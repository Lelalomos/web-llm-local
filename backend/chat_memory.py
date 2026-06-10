import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests


CHAT_MEMORY_DIR = Path(os.getenv("CHAT_MEMORY_DIR", "/data/chat_memory"))
ACTIVE_SESSION_DIR = CHAT_MEMORY_DIR / "active_sessions"
ARCHIVE_SESSION_DIR = CHAT_MEMORY_DIR / "sessions"
CHAT_MEMORY_FILE = CHAT_MEMORY_DIR / "summary_notes.md"
MAX_MEMORY_PROMPT_CHARS = int(os.getenv("CHAT_MEMORY_PROMPT_CHARS", "12000"))
MAX_SUMMARY_TRANSCRIPT_CHARS = int(os.getenv("CHAT_MEMORY_TRANSCRIPT_CHARS", "20000"))
SUMMARY_RAG_ENABLED = os.getenv("CHAT_MEMORY_SUMMARY_RAG_ENABLED", "true").lower() not in {"0", "false", "no", "off"}
SUMMARY_RAG_MAX_CHARS = int(os.getenv("CHAT_MEMORY_SUMMARY_RAG_CHARS", "6000"))
AUTO_SUMMARY_IDLE_SECONDS = int(os.getenv("CHAT_MEMORY_IDLE_SECONDS", "900"))
DEFAULT_SESSION_ID = "session"
MEMORY_RAG_STOPWORDS = {
    "user",
    "assistant",
    "what",
    "your",
    "this",
    "that",
    "with",
    "from",
    "have",
    "will",
    "about",
    "their",
    "they",
    "them",
}

CHAT_SUMMARY_PROMPT = (
    "You are creating persistent memory notes about the user. "
    "Write a detailed markdown summary with these sections exactly: "
    "## Session Goal, ## Important Facts, ## User Preferences, ## Personal Style, ## Open Questions, ## Useful Follow-ups. "
    "Keep it factual. Do not invent details. Include concrete details that would help future chats understand the user better. "
    "Do not include session ids, model names, task mode names, timestamps, or backend metadata."
)


def ensure_chat_memory_dirs() -> None:
    ACTIVE_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_SESSION_DIR.mkdir(parents=True, exist_ok=True)


def normalize_session_id(session_id: str | None) -> str:
    raw_value = (session_id or DEFAULT_SESSION_ID).strip().lower()
    normalized = re.sub(r"[^a-z0-9_-]+", "-", raw_value).strip("-")
    return normalized or DEFAULT_SESSION_ID


def build_memory_system_prompt(memory_text: str) -> str:
    return (
        "Use the following long-term notes about the user to adapt your answers. "
        "Treat these notes as helpful memory, not as absolute truth if the current chat contradicts them. "
        "Always follow the current request's topic, programming language, and output format over older memory notes. "
        "Prefer concrete remembered facts about the user, such as a stated name, over notes that only say the assistant did not know something. "
        "Do not treat a past assistant failure to remember as proof that the fact is unknown if another memory note contains the fact.\n\n"
        f"{memory_text}"
    )


def load_memory_text(max_chars: int | None = None, transcript: str = "") -> str:
    memory_text = load_full_memory_text()
    if not memory_text:
        return ""

    prompt_chars = MAX_MEMORY_PROMPT_CHARS if max_chars is None else max(0, int(max_chars))
    if prompt_chars <= 0:
        return ""

    if len(memory_text) <= prompt_chars:
        return memory_text

    if transcript:
        selected_text = select_summary_rag_context(memory_text, transcript, prompt_chars)
        if selected_text:
            return "[Relevant memory selected]\n\n" + selected_text

    truncated_text = memory_text[-prompt_chars:].lstrip()
    return "[Earlier memory truncated]\n\n" + truncated_text


def load_full_memory_text() -> str:
    if not CHAT_MEMORY_FILE.exists():
        return ""

    return CHAT_MEMORY_FILE.read_text(encoding="utf-8").strip()


def inject_memory_context(payload: dict, max_chars: int | None = None) -> bool:
    memory_text = load_memory_text(max_chars, build_chat_transcript(payload.get("messages", [])))
    if not memory_text:
        return False

    memory_prompt = build_memory_system_prompt(memory_text)
    for message in payload.get("messages", []):
        if message.get("role") == "system":
            message["content"] = f"{memory_prompt}\n\n{message['content']}"
            return True

    payload.setdefault("messages", []).insert(0, {"role": "system", "content": memory_prompt})
    return True


def build_chat_transcript(messages: list[dict]) -> str:
    lines = []
    for message in messages:
        role = str(message.get("role", "unknown")).upper()
        content = str(message.get("content", "")).strip()
        if content:
            lines.append(f"{role}: {content}")

    transcript = "\n\n".join(lines).strip()
    if len(transcript) <= MAX_SUMMARY_TRANSCRIPT_CHARS:
        return transcript

    return transcript[:MAX_SUMMARY_TRANSCRIPT_CHARS].rstrip() + "\n\n[Transcript truncated for summary generation.]"


def _tokenize_for_memory_rag(text: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[A-Za-z0-9_ก-๙]{4,}", text) if token.lower() not in MEMORY_RAG_STOPWORDS}


def select_summary_rag_context(memory_text: str, transcript: str, max_chars: int) -> str:
    memory_text = memory_text.strip()
    if not memory_text or max_chars <= 0:
        return ""
    if len(memory_text) <= max_chars:
        return memory_text

    transcript_tokens = _tokenize_for_memory_rag(transcript)
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", memory_text) if chunk.strip()]
    if not chunks:
        return memory_text[-max_chars:].lstrip()

    scored_chunks = []
    for index, chunk in enumerate(chunks):
        chunk_tokens = _tokenize_for_memory_rag(chunk)
        score = len(transcript_tokens & chunk_tokens)
        scored_chunks.append((score, index, chunk))

    relevant_chunks = [(score, index, chunk) for score, index, chunk in scored_chunks if score > 0]
    if not relevant_chunks:
        return memory_text[-max_chars:].lstrip()

    selected = []
    remaining_chars = max_chars
    for _score, index, chunk in sorted(relevant_chunks, key=lambda item: (-item[0], item[1])):
        chunk_with_spacing = chunk if not selected else "\n\n" + chunk
        if len(chunk_with_spacing) > remaining_chars:
            continue
        selected.append((index, chunk))
        remaining_chars -= len(chunk_with_spacing)
        if remaining_chars <= 0:
            break

    if not selected:
        return memory_text[-max_chars:].lstrip()

    return "\n\n".join(chunk for _index, chunk in sorted(selected)).strip()


def summarize_chat_session(ollama_url: str, model: str, messages: list[dict], task_mode: str, summary_prompt: str | None = None) -> str:
    transcript = build_chat_transcript(messages)
    existing_memory = load_full_memory_text() if SUMMARY_RAG_ENABLED else ""
    summary_rag_context = select_summary_rag_context(existing_memory, transcript, SUMMARY_RAG_MAX_CHARS)
    user_prompt = "Summarize the recent finished chat session for long-term user memory."
    if summary_rag_context:
        user_prompt += (
            "\n\nExisting relevant long-term memory notes. Use them only to preserve stable facts and avoid contradictions:\n\n"
            f"{summary_rag_context}"
        )
    user_prompt += f"\n\nRecent finished chat transcript:\n\n{transcript}"
    summary_payload = {
        "model": model,
        "stream": False,
        "think": False,
        "options": {"num_predict": 700},
        "messages": [
            {"role": "system", "content": (summary_prompt or CHAT_SUMMARY_PROMPT).strip()},
            {"role": "user", "content": user_prompt},
        ],
    }
    response = requests.post(f"{ollama_url}/api/chat", json=summary_payload, timeout=120)
    response.raise_for_status()
    response_json = response.json()
    return str(response_json.get("message", {}).get("content", "")).strip()


def _session_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def _session_iso_timestamp() -> str:
    return datetime.now(UTC).isoformat()


def _active_session_path(session_id: str) -> Path:
    ensure_chat_memory_dirs()
    return ACTIVE_SESSION_DIR / f"{normalize_session_id(session_id)}.json"


def _archive_session_path(session_id: str) -> Path:
    ensure_chat_memory_dirs()
    return ARCHIVE_SESSION_DIR / f"{_session_timestamp()}-{normalize_session_id(session_id)}.json"


def load_active_session(session_id: str) -> dict | None:
    session_path = _active_session_path(session_id)
    if not session_path.exists():
        return None

    return json.loads(session_path.read_text(encoding="utf-8"))


def upsert_active_session(session_id: str, model: str, task_mode: str, messages: list[dict]) -> Path:
    ensure_chat_memory_dirs()
    now = _session_iso_timestamp()
    session_payload = {
        "session_id": normalize_session_id(session_id),
        "model": model,
        "task_mode": task_mode or "general",
        "messages": messages,
        "message_count": len(messages),
        "created_at": now,
        "updated_at": now,
    }

    existing_session = load_active_session(session_id)
    if existing_session:
        session_payload["created_at"] = existing_session.get("created_at", now)

    session_path = _active_session_path(session_id)
    session_path.write_text(json.dumps(session_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return session_path


def append_summary_note(session_id: str, model: str, task_mode: str, summary: str) -> Path:
    ensure_chat_memory_dirs()
    entry = summary.strip()
    existing_text = CHAT_MEMORY_FILE.read_text(encoding="utf-8") if CHAT_MEMORY_FILE.exists() else ""
    separator = "" if not existing_text.strip() else "\n\n"
    CHAT_MEMORY_FILE.write_text(existing_text.rstrip() + separator + entry + "\n", encoding="utf-8")
    return CHAT_MEMORY_FILE


def clear_chat_memory() -> dict:
    ensure_chat_memory_dirs()
    summary_removed = False
    active_removed = 0
    archived_removed = 0

    if CHAT_MEMORY_FILE.exists():
        CHAT_MEMORY_FILE.unlink()
        summary_removed = True

    for session_path in ACTIVE_SESSION_DIR.glob("*.json"):
        if session_path.is_file():
            session_path.unlink()
            active_removed += 1

    for session_path in ARCHIVE_SESSION_DIR.glob("*.json"):
        if session_path.is_file():
            session_path.unlink()
            archived_removed += 1

    ensure_chat_memory_dirs()
    return {
        "summary_removed": summary_removed,
        "active_sessions_removed": active_removed,
        "archived_sessions_removed": archived_removed,
    }


def archive_summarized_session(session_payload: dict, summary: str) -> Path:
    archive_payload = dict(session_payload)
    archive_payload["summary"] = summary
    archive_payload["summarized_at"] = _session_iso_timestamp()
    archive_path = _archive_session_path(str(session_payload.get("session_id", DEFAULT_SESSION_ID)))
    archive_path.write_text(json.dumps(archive_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return archive_path


def finalize_session(session_payload: dict, ollama_url: str, summary_prompt: str | None = None) -> dict:
    summary = summarize_chat_session(
        ollama_url,
        str(session_payload.get("model", "")),
        list(session_payload.get("messages", [])),
        str(session_payload.get("task_mode", "general")),
        summary_prompt,
    )
    archive_path = archive_summarized_session(session_payload, summary)
    memory_path = append_summary_note(
        str(session_payload.get("session_id", DEFAULT_SESSION_ID)),
        str(session_payload.get("model", "")),
        str(session_payload.get("task_mode", "general")),
        summary,
    )
    active_path = _active_session_path(str(session_payload.get("session_id", DEFAULT_SESSION_ID)))
    if active_path.exists():
        active_path.unlink()
    return {
        "summary": summary,
        "archive_path": archive_path,
        "memory_path": memory_path,
    }


def _is_session_stale(session_payload: dict, now: datetime, idle_seconds: int) -> bool:
    updated_at = session_payload.get("updated_at")
    if not updated_at:
        return False

    updated_dt = datetime.fromisoformat(updated_at)
    return now - updated_dt >= timedelta(seconds=idle_seconds)


def summarize_stale_sessions(ollama_url: str, current_session_id: str | None = None, summary_prompt: str | None = None) -> list[dict]:
    ensure_chat_memory_dirs()
    now = datetime.now(UTC)
    summaries = []
    current_id = normalize_session_id(current_session_id)

    for session_path in sorted(ACTIVE_SESSION_DIR.glob("*.json")):
        session_payload = json.loads(session_path.read_text(encoding="utf-8"))
        session_id = normalize_session_id(str(session_payload.get("session_id", DEFAULT_SESSION_ID)))
        if session_id == current_id:
            continue
        if not _is_session_stale(session_payload, now, AUTO_SUMMARY_IDLE_SECONDS):
            continue

        result = finalize_session(session_payload, ollama_url, summary_prompt)
        summaries.append(
            {
                "session_id": session_id,
                "archive_path": str(result["archive_path"]),
                "memory_path": str(result["memory_path"]),
            }
        )

    return summaries
