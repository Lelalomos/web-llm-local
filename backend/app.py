import os
import json
import threading
import re
from copy import deepcopy
import requests
from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.responses import StreamingResponse
from chat_memory import clear_chat_memory, finalize_session, inject_memory_context, load_active_session, summarize_stale_sessions, upsert_active_session
from config_store import load_app_config, save_app_config
from document_utils import extract_document_text_with_metadata
from intent_router import infer_chat_intent
from model_bootstrap import DEFAULT_OLLAMA_MODEL, ensure_default_model_available
from ollama_options import apply_gpu_defaults
from search_policy import should_auto_search
from search_enhancer import enhance_search_context
from skill_loader import ensure_skill_dir, inject_skill_context
from task_modes import apply_task_mode
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Lightweight LLM Gateway")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
AUTO_SUMMARY_CHECK_SECONDS = int(os.getenv("CHAT_MEMORY_CHECK_SECONDS", "60"))
CONTINUE_RESPONSE_PROMPT = (
    "Continue from the exact next line of the previous answer. "
    "Do not repeat prior text. If you were inside a code block, continue that same code block. "
    "If the previous answer was prose, continue the same answer naturally."
)
summary_worker_stop_event = threading.Event()
summary_worker_lock = threading.Lock()
summary_worker_thread = None
bootstrap_worker_thread = None
MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._:/-]+$")

# Proxy to get available models
@app.get("/api/tags")
def get_tags():
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Ollama server offline: {e}")


@app.get("/api/config")
def get_config():
    return load_app_config()


@app.post("/api/config")
def update_config(payload: dict = Body(...)):
    return save_app_config(payload)


def _normalize_model_name(payload: dict) -> str:
    model = str(payload.get("model", "")).strip()
    if not model:
        raise HTTPException(status_code=400, detail="model is required")
    if not MODEL_NAME_PATTERN.fullmatch(model):
        raise HTTPException(status_code=400, detail="invalid model name")
    return model


def _ollama_json_request(path: str, payload: dict, timeout: int = 120, method: str = "POST") -> dict:
    response = requests.request(method, f"{OLLAMA_URL}{path}", json=payload, timeout=timeout)
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)
    if not response.text.strip():
        return {"status": "success"}
    try:
        return response.json()
    except requests.exceptions.JSONDecodeError:
        return {"status": response.text.strip()}


@app.post("/api/models/pull")
def pull_model(payload: dict = Body(...)):
    model = _normalize_model_name(payload)
    result = _ollama_json_request("/api/pull", {"model": model, "stream": False}, timeout=1800)
    return {"model": model, "status": result.get("status", "success")}


@app.post("/api/models/delete")
def delete_model(payload: dict = Body(...)):
    model = _normalize_model_name(payload)
    result = _ollama_json_request("/api/delete", {"model": model}, timeout=120, method="DELETE")
    return {"model": model, "status": result.get("status", "success")}

# Parse document and return extracted text
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    filename = file.filename
    content = await file.read()

    try:
        extracted_text, character_count, extraction_metadata = extract_document_text_with_metadata(filename, content, load_app_config(), OLLAMA_URL)
        return {
            "filename": filename,
            "text": extracted_text,
            "character_count": character_count,
            **extraction_metadata,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing file: {e}")

from search_service import build_direct_url_context, execute_web_search


def _apply_default_model(payload: dict, app_config: dict) -> None:
    if str(payload.get("model", "")).strip():
        return

    default_model = str(app_config.get("default_model", "")).strip()
    if default_model:
        payload["model"] = default_model


def _apply_config_defaults(payload: dict, app_config: dict) -> None:
    default_system_prompt = str(app_config.get("default_system_prompt", "")).strip()
    if default_system_prompt:
        for message in payload.get("messages", []):
            if message.get("role") == "system":
                message["content"] = f"{default_system_prompt}\n\n{message.get('content', '')}".strip()
                break
        else:
            payload.setdefault("messages", []).insert(0, {"role": "system", "content": default_system_prompt})

    default_options = app_config.get("default_options", {})
    options = payload.setdefault("options", {})
    for key, value in default_options.items():
        options.setdefault(key, value)


def _search_requested(payload: dict, app_config: dict, task_mode: str = "general", direct_context_used: bool = False) -> bool:
    search_mode = payload.pop("web_search_mode", None)
    legacy_web_search = payload.pop("web_search", None)

    if search_mode == "on":
        return True
    if search_mode == "off":
        return False
    if isinstance(legacy_web_search, bool):
        return legacy_web_search
    if direct_context_used:
        return False
    if _is_document_prompt(payload):
        return False
    if task_mode in {"code_writer", "code_editor", "bug_fixer"}:
        return False

    default_search_mode = app_config.get("default_web_search_mode", "auto")
    if default_search_mode == "on":
        return True
    if default_search_mode == "off":
        return False

    messages = payload.get("messages") or []
    if not messages:
        return False

    latest_message = messages[-1]
    if latest_message.get("role") != "user":
        return False

    latest_content = str(latest_message.get("content", ""))
    inferred_intent = infer_chat_intent(OLLAMA_URL, latest_content, task_mode, app_config)
    inferred_web_search = bool(inferred_intent.get("web_search", should_auto_search(latest_content)))
    if inferred_web_search and inferred_intent.get("search_query"):
        payload["_web_search_query"] = inferred_intent["search_query"]
    return inferred_web_search


def _search_status_line(search_used: bool) -> str:
    return json.dumps({"type": "search_status", "search_used": search_used}) + "\n"


def _stream_error_line(message: str) -> str:
    return json.dumps({"type": "stream_error", "message": message}) + "\n"


def _is_document_prompt(payload: dict) -> bool:
    messages = payload.get("messages") or []
    if not messages:
        return False

    latest_message = messages[-1]
    if latest_message.get("role") != "user":
        return False

    content = str(latest_message.get("content", ""))
    return content.startswith('Context from uploaded file "') and "Use the file content above to answer this prompt:" in content


def _apply_document_chat_defaults(payload: dict) -> None:
    if _is_document_prompt(payload) and "think" not in payload:
        payload["think"] = False


def _apply_thinking_defaults(payload: dict) -> None:
    if "think" not in payload:
        payload["think"] = False


def _normalize_session_payload(payload: dict) -> tuple[str, str, list[dict], str]:
    model = str(payload.get("model", "")).strip()
    if not model:
        raise HTTPException(status_code=400, detail="model is required")

    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=400, detail="messages are required")

    session_id = str(payload.get("session_id", "")).strip() or "session"
    task_mode = str(payload.get("task_mode", "general")).strip() or "general"
    return model, session_id, messages, task_mode


def _persist_completed_chat(session_id: str, model: str, task_mode: str, messages: list[dict], assistant_content: str) -> None:
    if not assistant_content.strip():
        return

    completed_messages = list(messages) + [{"role": "assistant", "content": assistant_content}]
    upsert_active_session(session_id, model, task_mode, completed_messages)


def _run_pending_summaries(current_session_id: str | None = None) -> None:
    if not summary_worker_lock.acquire(blocking=False):
        return

    try:
        app_config = load_app_config()
        summarize_stale_sessions(OLLAMA_URL, current_session_id, str(app_config.get("chat_summary_prompt", "")))
    finally:
        summary_worker_lock.release()


def _summary_worker_loop() -> None:
    while not summary_worker_stop_event.wait(AUTO_SUMMARY_CHECK_SECONDS):
        _run_pending_summaries()


def _bootstrap_model_loop() -> None:
    try:
        ensure_default_model_available(OLLAMA_URL, DEFAULT_OLLAMA_MODEL)
    except requests.exceptions.RequestException:
        return


@app.on_event("startup")
def startup_event():
    global summary_worker_thread, bootstrap_worker_thread
    ensure_skill_dir()
    summary_worker_stop_event.clear()
    summary_worker_thread = threading.Thread(target=_summary_worker_loop, name="chat-summary-worker", daemon=True)
    summary_worker_thread.start()
    bootstrap_worker_thread = threading.Thread(target=_bootstrap_model_loop, name="ollama-bootstrap-worker", daemon=True)
    bootstrap_worker_thread.start()


@app.on_event("shutdown")
def shutdown_event():
    summary_worker_stop_event.set()
    if summary_worker_thread and summary_worker_thread.is_alive():
        summary_worker_thread.join(timeout=2)
    if bootstrap_worker_thread and bootstrap_worker_thread.is_alive():
        bootstrap_worker_thread.join(timeout=2)


def _inject_search_context(payload: dict, web_search_enabled: bool, app_config: dict) -> bool:
    if not web_search_enabled or "messages" not in payload or not payload["messages"]:
        return False

    latest_message = payload["messages"][-1]
    if latest_message.get("role") != "user":
        return False

    query = payload.pop("_web_search_query", None) or latest_message.get("content", "")
    search_context, search_results = execute_web_search(query, app_config)
    search_context, enhanced, enhancer_model = enhance_search_context(OLLAMA_URL, str(query), search_context, search_results, app_config)
    if enhanced:
        print(f"[Search Service] Enhanced search context with small model: {enhancer_model}")
    max_chars = int(app_config.get("web_search_context_max_chars", 0) or 0)
    if max_chars > 0 and len(search_context) > max_chars:
        search_context = search_context[:max_chars].rstrip() + "\n\n[Web search context truncated to fit config limits.]"

    if not search_context or search_context == "No web search results found.":
        return False

    search_system_prompt = (
        "Use the following Web Search results to help answer the user's question:\n\n"
        f"{search_context}\n\n"
        "Provide citations for the URLs when referencing them."
    )

    for msg in payload["messages"]:
        if msg.get("role") == "system":
            msg["content"] = msg["content"] + "\n\n" + search_system_prompt
            return True

    payload["messages"].insert(0, {"role": "system", "content": search_system_prompt})
    return True


def _should_inject_memory_context(task_mode: str, web_search_enabled: bool, app_config: dict, is_document_prompt: bool = False) -> bool:
    if web_search_enabled:
        return False

    memory_used = app_config.get("memory_used", {})
    if is_document_prompt:
        if isinstance(memory_used, dict) and "upload_file" in memory_used:
            return bool(memory_used.get("upload_file"))
        return False

    if isinstance(memory_used, dict) and task_mode in memory_used:
        return bool(memory_used.get(task_mode))
    return task_mode == "general"


@app.post("/api/task-mode/infer")
def infer_task_mode(payload: dict = Body(...)):
    app_config = load_app_config()
    prompt = str(payload.get("prompt", "")).strip()
    current_task_mode = str(payload.get("current_task_mode", "general")).strip() or "general"
    intent = infer_chat_intent(OLLAMA_URL, prompt, current_task_mode, app_config)
    return {
        "task_mode": intent["task_mode"],
        "web_search": bool(intent.get("web_search", False)),
        "search_query": str(intent.get("search_query", "")),
        "source": intent.get("source", "fallback"),
    }


def _inject_direct_url_context(payload: dict, app_config: dict) -> bool:
    messages = payload.get("messages") or []
    if not messages:
        return False

    latest_message = messages[-1]
    if latest_message.get("role") != "user":
        return False

    max_chars = int(app_config.get("web_search_context_max_chars", 0) or 0)
    website_context, used_urls = build_direct_url_context(str(latest_message.get("content", "")), max_chars)
    if not website_context:
        return False

    url_context_prompt = (
        "Use the following Website Context from the exact URL(s) provided by the user. "
        "Prefer this direct page context over general web search snippets. "
        "Cite the URL(s) when referencing page content.\n\n"
        f"{website_context}"
    )

    for message in payload.get("messages", []):
        if message.get("role") == "system":
            message["content"] = f"{message.get('content', '')}\n\n{url_context_prompt}".strip()
            return True

    payload.setdefault("messages", []).insert(0, {"role": "system", "content": url_context_prompt})
    return bool(used_urls)


def _should_continue_response(task_mode: str, search_used: bool, response_json: dict, assistant_content: str = "") -> bool:
    message = response_json.get("message", {})
    response_content = assistant_content or message.get("content", "")
    return response_json.get("done_reason") == "length" and bool(response_content)


def _build_continuation_payload(payload: dict, assistant_content: str) -> dict:
    continuation_payload = deepcopy(payload)
    continuation_payload["messages"] = list(continuation_payload.get("messages", [])) + [
        {"role": "assistant", "content": assistant_content},
        {"role": "user", "content": CONTINUE_RESPONSE_PROMPT},
    ]
    continuation_payload["stream"] = False
    return continuation_payload


def _merge_response_content(base_response: dict, continuation_response: dict) -> dict:
    base_message = base_response.setdefault("message", {})
    continuation_message = continuation_response.get("message", {})
    base_content = base_message.get("content", "")
    continuation_content = continuation_message.get("content", "")

    if base_content and continuation_content and not continuation_content.startswith("\n"):
        base_message["content"] = f"{base_content}\n{continuation_content}"
    else:
        base_message["content"] = f"{base_content}{continuation_content}"

    base_response["done"] = continuation_response.get("done", base_response.get("done"))
    base_response["done_reason"] = continuation_response.get("done_reason", base_response.get("done_reason"))
    base_response["eval_count"] = base_response.get("eval_count", 0) + continuation_response.get("eval_count", 0)
    base_response["eval_duration"] = base_response.get("eval_duration", 0) + continuation_response.get("eval_duration", 0)
    base_response["total_duration"] = base_response.get("total_duration", 0) + continuation_response.get("total_duration", 0)
    return base_response


def _post_ollama_chat(payload: dict, stream: bool):
    return requests.post(
        f"{OLLAMA_URL}/api/chat",
        json=payload,
        stream=stream,
        timeout=120
    )


def _complete_non_stream_chat(payload: dict, task_mode: str, search_used: bool, max_continuations: int) -> dict:
    current_payload = deepcopy(payload)
    current_payload["stream"] = False
    response = _post_ollama_chat(current_payload, stream=False)

    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    response_json = response.json()
    for _ in range(max_continuations):
        if not _should_continue_response(task_mode, search_used, response_json):
            break

        continuation_payload = _build_continuation_payload(current_payload, response_json.get("message", {}).get("content", ""))
        continuation_response = _post_ollama_chat(continuation_payload, stream=False)
        if continuation_response.status_code != 200:
            break

        continuation_json = continuation_response.json()
        response_json = _merge_response_content(response_json, continuation_json)
        current_payload = continuation_payload

    return response_json


def _stream_chat_chunks(payload: dict, task_mode: str, session_id: str, persisted_messages: list[dict], search_used: bool, max_continuations: int):
    current_payload = deepcopy(payload)
    current_payload["stream"] = True
    final_response_json = {}
    full_response_parts = []

    for _ in range(max_continuations + 1):
        response = _post_ollama_chat(current_payload, stream=True)
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        current_content_parts = []
        response_json = {}

        for line in response.iter_lines():
            if not line:
                continue

            decoded_line = line.decode("utf-8")
            try:
                parsed = json.loads(decoded_line)
                content = parsed.get("message", {}).get("content", "")
                if content:
                    current_content_parts.append(content)
                    full_response_parts.append(content)
                response_json = parsed
            except json.JSONDecodeError:
                pass

            yield decoded_line + "\n"

        if final_response_json:
            final_response_json = _merge_response_content(final_response_json, response_json)
        else:
            final_response_json = response_json

        if not _should_continue_response(task_mode, search_used, response_json, "".join(current_content_parts)):
            break

        current_payload = _build_continuation_payload(current_payload, "".join(current_content_parts))
        current_payload["stream"] = True

    _persist_completed_chat(
        session_id,
        str(payload.get("model", "")),
        task_mode,
        persisted_messages,
        "".join(full_response_parts),
    )

@app.post("/api/chat")
def chat(payload: dict = Body(...)):
    app_config = load_app_config()
    _apply_default_model(payload, app_config)
    model, session_id, messages, _ = _normalize_session_payload(payload)
    persisted_messages = deepcopy(messages)
    payload.pop("session_id", None)
    _apply_config_defaults(payload, app_config)
    apply_gpu_defaults(payload)
    is_document_prompt = _is_document_prompt(payload)
    if not is_document_prompt:
        _run_pending_summaries(session_id)
    _apply_document_chat_defaults(payload)
    _apply_thinking_defaults(payload)
    task_mode = apply_task_mode(payload)
    if not is_document_prompt and app_config.get("skill_markdown_enabled", True):
        inject_skill_context(payload, int(app_config.get("skill_prompt_max_chars", 0) or 0))

    # 1. Check if Web Search is requested
    direct_context_used = _inject_direct_url_context(payload, app_config)
    web_search_enabled = _search_requested(payload, app_config, task_mode, direct_context_used)
    if _should_inject_memory_context(task_mode, web_search_enabled, app_config, is_document_prompt):
        inject_memory_context(payload)
    search_used = _inject_search_context(payload, web_search_enabled, app_config)
    max_continuations = int(app_config.get("chat_max_continuations", 0) or 0)
                    
    # 2. Forward request to Ollama
    stream = payload.get("stream", False)
    try:
        if stream:
            def generate_stream():
                yield _search_status_line(search_used)
                try:
                    for line in _stream_chat_chunks(payload, task_mode, session_id, persisted_messages, search_used, max_continuations):
                        yield line
                except requests.exceptions.RequestException as e:
                    yield _stream_error_line(f"Ollama connection error: {e}")
                except HTTPException as e:
                    yield _stream_error_line(str(e.detail))
            return StreamingResponse(generate_stream(), media_type="application/x-ndjson")
        else:
            response_json = _complete_non_stream_chat(payload, task_mode, search_used, max_continuations)
            response_json["search_used"] = search_used
            _persist_completed_chat(
                session_id,
                model,
                task_mode,
                persisted_messages,
                str(response_json.get("message", {}).get("content", "")),
            )
            return response_json
            
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Ollama connection error: {e}")


@app.post("/api/chat/end")
def end_chat(payload: dict = Body(...)):
    model, session_id, messages, task_mode = _normalize_session_payload(payload)

    try:
        app_config = load_app_config()
        session_payload = load_active_session(session_id) or {
            "session_id": session_id,
            "model": model,
            "task_mode": task_mode,
            "messages": messages,
        }
        result = finalize_session(session_payload, OLLAMA_URL, str(app_config.get("chat_summary_prompt", "")))
        return {
            "session_id": session_id,
            "summary": result["summary"],
            "session_file": str(result["archive_path"]),
            "memory_file": str(result["memory_path"]),
        }
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Ollama connection error: {e}")


@app.delete("/api/chat/memory")
def delete_chat_memory():
    return {
        "status": "cleared",
        **clear_chat_memory(),
    }
