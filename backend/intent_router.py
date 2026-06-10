import json
import re
from typing import Any

import requests

from search_policy import normalize_search_query, should_auto_search


ALLOWED_TASK_MODES = {"general", "code_writer", "code_reviewer", "code_editor", "bug_fixer"}
DEFAULT_INTENT_MODEL = "gemma2:2b"
CODE_WRITER_PATTERNS = (
    re.compile(r"\bwrite\b.*\b(code|api|endpoint|function|script|program|rust|python|javascript|typescript|go|java|c\+\+|sql)\b", re.I),
    re.compile(r"\b(create|build|implement|generate)\b.*\b(api|endpoint|function|script|program|service|server|client|code)\b", re.I),
    re.compile(r"\b(rust|python|javascript|typescript|go|java|c\+\+|sql)\b.*\b(api|endpoint|function|script|program|code)\b", re.I),
    re.compile(r"\bclass\b|\bfunction\b|\bendpoint\b|\bapi route\b|\bfastapi\b|\bexpress\b|\bactix\b|\baxum\b", re.I),
)


def fallback_task_mode(prompt: str, current_task_mode: str = "general") -> str:
    text = str(prompt or "").strip()
    if not text:
        return current_task_mode if current_task_mode in ALLOWED_TASK_MODES else "general"

    lowered = text.lower()
    if any(word in lowered for word in ("review this", "code review", "find bugs", "audit this code")):
        return "code_reviewer"
    if any(word in lowered for word in ("fix this bug", "debug this", "error", "traceback", "exception")):
        return "bug_fixer"
    if any(word in lowered for word in ("edit this code", "refactor this", "modify this code", "improve this code")):
        return "code_editor"
    if any(pattern.search(text) for pattern in CODE_WRITER_PATTERNS):
        return "code_writer"
    return "general"


def fallback_intent(prompt: str, current_task_mode: str = "general") -> dict[str, Any]:
    search_query = normalize_search_query(prompt)
    return {
        "task_mode": fallback_task_mode(prompt, current_task_mode),
        "web_search": should_auto_search(prompt),
        "search_query": search_query,
        "source": "fallback",
    }


def _extract_json_object(text: str) -> dict[str, Any] | None:
    cleaned = str(text or "").strip()
    if not cleaned:
        return None

    try:
        parsed = json.loads(cleaned)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        return None

    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _normalize_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1", "on"}:
            return True
        if lowered in {"false", "no", "0", "off"}:
            return False
    return default


def _normalize_model_intent(raw_intent: dict[str, Any], prompt: str, current_task_mode: str) -> dict[str, Any] | None:
    task_mode = str(raw_intent.get("task_mode", "")).strip()
    if task_mode not in ALLOWED_TASK_MODES:
        return None

    fallback = fallback_intent(prompt, current_task_mode)
    fallback_task_mode_value = str(fallback.get("task_mode", "general"))
    if fallback_task_mode_value != "general" and task_mode == "general":
        task_mode = fallback_task_mode_value

    search_query = str(raw_intent.get("search_query", "")).strip()
    if not search_query:
        search_query = fallback["search_query"]

    web_search = _normalize_bool(raw_intent.get("web_search"), fallback["web_search"])
    if fallback["web_search"]:
        web_search = True
    if task_mode in {"code_writer", "code_editor", "bug_fixer"} and not fallback["web_search"]:
        web_search = False

    return {
        "task_mode": task_mode,
        "web_search": web_search,
        "search_query": normalize_search_query(search_query),
        "source": "model",
    }


def _build_intent_prompt(prompt: str, current_task_mode: str) -> str:
    return (
        "Classify the user's latest message for a local chat app.\n"
        "Return only valid JSON with these keys:\n"
        "- task_mode: one of general, code_writer, code_reviewer, code_editor, bug_fixer\n"
        "- web_search: boolean, true only when outside/current web information is needed\n"
        "- search_query: short search query, empty string if web_search is false\n\n"
        "Rules:\n"
        "- Relationship, life advice, explanation, or normal conversation is general.\n"
        "- New code/API/program/script generation is code_writer.\n"
        "- Reviewing existing code is code_reviewer.\n"
        "- Editing/refactoring existing code is code_editor.\n"
        "- Debugging errors or failures is bug_fixer.\n"
        "- Do not search web for normal coding requests unless the user asks for latest/current info.\n\n"
        f"Current selected task mode: {current_task_mode}\n"
        f"User message:\n{prompt[:4000]}"
    )


def infer_chat_intent(ollama_url: str, prompt: str, current_task_mode: str, app_config: dict) -> dict[str, Any]:
    if not app_config.get("task_mode_interpreter_enabled", True):
        return fallback_intent(prompt, current_task_mode)

    model = str(app_config.get("task_mode_interpreter_model") or DEFAULT_INTENT_MODEL).strip()
    timeout = int(app_config.get("task_mode_interpreter_timeout_seconds", 8) or 8)
    if not model:
        return fallback_intent(prompt, current_task_mode)

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _build_intent_prompt(prompt, current_task_mode)}],
        "stream": False,
        "think": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": 120,
            "num_gpu": 999,
        },
    }

    try:
        response = requests.post(f"{ollama_url}/api/chat", json=payload, timeout=timeout)
        response.raise_for_status()
        content = str(response.json().get("message", {}).get("content", ""))
    except (requests.exceptions.RequestException, ValueError, TypeError):
        return fallback_intent(prompt, current_task_mode)

    parsed = _extract_json_object(content)
    if not parsed:
        return fallback_intent(prompt, current_task_mode)

    normalized = _normalize_model_intent(parsed, prompt, current_task_mode)
    return normalized or fallback_intent(prompt, current_task_mode)
