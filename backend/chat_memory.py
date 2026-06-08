import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import requests


CHAT_MEMORY_DIR = Path(os.getenv("CHAT_MEMORY_DIR", "/app/data/chat_memory"))
ACTIVE_SESSION_DIR = CHAT_MEMORY_DIR / "active_sessions"
ARCHIVE_SESSION_DIR = CHAT_MEMORY_DIR / "sessions"
CHAT_MEMORY_FILE = CHAT_MEMORY_DIR / "summary_notes.md"
MAX_MEMORY_PROMPT_CHARS = int(os.getenv("CHAT_MEMORY_PROMPT_CHARS", "2000"))
MAX_SUMMARY_TRANSCRIPT_CHARS = int(os.getenv("CHAT_MEMORY_TRANSCRIPT_CHARS", "20000"))
AUTO_SUMMARY_IDLE_SECONDS = int(os.getenv("CHAT_MEMORY_IDLE_SECONDS", "900"))
DEFAULT_SESSION_ID = "session"

CHAT_SUMMARY_PROMPT = (
    "You are creating persistent memory notes about the user from one finished chat session. "
    "Write a detailed markdown summary with these sections exactly: "
    "## Session Goal, ## Important Facts, ## User Preferences, ## Personal Style, ## Open Questions, ## Useful Follow-ups. "
    "Keep it factual. Do not invent details. Include concrete details that would help future chats understand the user better."
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
        "Always follow the current request's topic, programming language, and output format over older memory notes.\n\n"
        f"{memory_text}"
    )


def load_memory_text() -> str:
    if not CHAT_MEMORY_FILE.exists():
        return ""

    memory_text = CHAT_MEMORY_FILE.read_text(encoding="utf-8").strip()
    if not memory_text:
        return ""

    if len(memory_text) <= MAX_MEMORY_PROMPT_CHARS:
        return memory_text

    truncated_text = memory_text[-MAX_MEMORY_PROMPT_CHARS:].lstrip()
    return "[Earlier memory truncated]\n\n" + truncated_text


def inject_memory_context(payload: dict) -> bool:
    memory_text = load_memory_text()
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


def summarize_chat_session(ollama_url: str, model: str, messages: list[dict], task_mode: str) -> str:
    transcript = build_chat_transcript(messages)
    summary_payload = {
        "model": model,
        "stream": False,
        "think": False,
        "options": {"num_predict": 700},
        "messages": [
            {"role": "system", "content": CHAT_SUMMARY_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Task mode: {task_mode or 'general'}\n\n"
                    "Summarize this finished chat session for long-term user memory.\n\n"
                    f"{transcript}"
                ),
            },
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
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    safe_session_id = normalize_session_id(session_id)
    entry = (
        f"\n# Session {timestamp}\n\n"
        f"- Session ID: `{safe_session_id}`\n"
        f"- Model: `{model}`\n"
        f"- Task Mode: `{task_mode or 'general'}`\n\n"
        f"{summary.strip()}\n"
    )
    existing_text = CHAT_MEMORY_FILE.read_text(encoding="utf-8") if CHAT_MEMORY_FILE.exists() else ""
    separator = "" if not existing_text.strip() else "\n\n---\n"
    CHAT_MEMORY_FILE.write_text(existing_text + separator + entry, encoding="utf-8")
    return CHAT_MEMORY_FILE


def archive_summarized_session(session_payload: dict, summary: str) -> Path:
    archive_payload = dict(session_payload)
    archive_payload["summary"] = summary
    archive_payload["summarized_at"] = _session_iso_timestamp()
    archive_path = _archive_session_path(str(session_payload.get("session_id", DEFAULT_SESSION_ID)))
    archive_path.write_text(json.dumps(archive_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return archive_path


def finalize_session(session_payload: dict, ollama_url: str) -> dict:
    summary = summarize_chat_session(
        ollama_url,
        str(session_payload.get("model", "")),
        list(session_payload.get("messages", [])),
        str(session_payload.get("task_mode", "general")),
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


def summarize_stale_sessions(ollama_url: str, current_session_id: str | None = None) -> list[dict]:
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

        result = finalize_session(session_payload, ollama_url)
        summaries.append(
            {
                "session_id": session_id,
                "archive_path": str(result["archive_path"]),
                "memory_path": str(result["memory_path"]),
            }
        )

    return summaries
