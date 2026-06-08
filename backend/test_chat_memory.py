import json
import tempfile
import unittest
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import chat_memory


class ChatMemoryTests(unittest.TestCase):
    def test_inject_memory_context_prepends_system_message(self):
        payload = {"messages": [{"role": "user", "content": "hello"}]}

        with patch("chat_memory.load_memory_text", return_value="# Session\nUser likes concise answers"):
            injected = chat_memory.inject_memory_context(payload)

        self.assertTrue(injected)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("User likes concise answers", payload["messages"][0]["content"])
        self.assertIn("Always follow the current request", payload["messages"][0]["content"])

    def test_build_chat_transcript_limits_large_input(self):
        messages = [{"role": "user", "content": "a" * (chat_memory.MAX_SUMMARY_TRANSCRIPT_CHARS + 50)}]

        transcript = chat_memory.build_chat_transcript(messages)

        self.assertIn("[Transcript truncated", transcript)

    def test_load_memory_text_limits_prompt_context(self):
        with _temporary_memory_paths():
            chat_memory.ensure_chat_memory_dirs()
            chat_memory.CHAT_MEMORY_FILE.write_text("a" * (chat_memory.MAX_MEMORY_PROMPT_CHARS + 50), encoding="utf-8")

            memory_text = chat_memory.load_memory_text()

        self.assertLessEqual(len(memory_text), chat_memory.MAX_MEMORY_PROMPT_CHARS + len("[Earlier memory truncated]\n\n"))
        self.assertIn("[Earlier memory truncated]", memory_text)

    def test_upsert_active_session_writes_pending_file(self):
        with _temporary_memory_paths():
            chat_memory.ensure_chat_memory_dirs()
            session_path = chat_memory.upsert_active_session(
                session_id="chat-1",
                model="gemma4:e2b",
                task_mode="general",
                messages=[{"role": "user", "content": "hello"}],
            )

            self.assertTrue(session_path.exists())
            payload = json.loads(session_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["session_id"], "chat-1")
            self.assertEqual(payload["message_count"], 1)

    def test_finalize_session_archives_and_removes_active_file(self):
        with _temporary_memory_paths():
            chat_memory.ensure_chat_memory_dirs()
            session_path = chat_memory.upsert_active_session(
                session_id="chat-2",
                model="gemma4:e2b",
                task_mode="general",
                messages=[{"role": "user", "content": "hello"}],
            )
            session_payload = json.loads(session_path.read_text(encoding="utf-8"))

            with patch("chat_memory.summarize_chat_session", return_value="## Session Goal\nSay hello"):
                result = chat_memory.finalize_session(session_payload, "http://ollama:11434")

            self.assertFalse(session_path.exists())
            self.assertTrue(result["archive_path"].exists())
            self.assertTrue(result["memory_path"].exists())
            self.assertIn("## Session Goal", result["memory_path"].read_text(encoding="utf-8"))

    def test_summarize_stale_sessions_only_processes_old_pending_files(self):
        with _temporary_memory_paths():
            chat_memory.ensure_chat_memory_dirs()
            now = datetime.now(UTC)
            old_payload = {
                "session_id": "old-chat",
                "model": "gemma4:e2b",
                "task_mode": "general",
                "messages": [{"role": "user", "content": "hello"}],
                "updated_at": (now - timedelta(seconds=chat_memory.AUTO_SUMMARY_IDLE_SECONDS + 30)).isoformat(),
                "created_at": now.isoformat(),
            }
            current_payload = {
                "session_id": "current-chat",
                "model": "gemma4:e2b",
                "task_mode": "general",
                "messages": [{"role": "user", "content": "still active"}],
                "updated_at": now.isoformat(),
                "created_at": now.isoformat(),
            }
            (chat_memory.ACTIVE_SESSION_DIR / "old-chat.json").write_text(json.dumps(old_payload), encoding="utf-8")
            (chat_memory.ACTIVE_SESSION_DIR / "current-chat.json").write_text(json.dumps(current_payload), encoding="utf-8")

            with patch("chat_memory.summarize_chat_session", return_value="## Session Goal\nOld summary"):
                results = chat_memory.summarize_stale_sessions("http://ollama:11434", "current-chat")

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["session_id"], "old-chat")
            self.assertFalse((chat_memory.ACTIVE_SESSION_DIR / "old-chat.json").exists())
            self.assertTrue((chat_memory.ACTIVE_SESSION_DIR / "current-chat.json").exists())

    def test_summarize_chat_session_returns_model_content(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"message": {"content": "## Session Goal\nBuild a tool"}}

        with patch("chat_memory.requests.post", return_value=FakeResponse()) as mocked_post:
            summary = chat_memory.summarize_chat_session(
                "http://ollama:11434",
                "gemma4:e2b",
                [{"role": "user", "content": "hello"}],
                "general",
            )

        self.assertIn("## Session Goal", summary)
        self.assertEqual(mocked_post.call_count, 1)


@contextmanager
def _temporary_memory_paths():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        with patch.multiple(
            chat_memory,
            CHAT_MEMORY_DIR=temp_root,
            ACTIVE_SESSION_DIR=temp_root / "active_sessions",
            ARCHIVE_SESSION_DIR=temp_root / "sessions",
            CHAT_MEMORY_FILE=temp_root / "summary_notes.md",
        ):
            yield


if __name__ == "__main__":
    unittest.main()
