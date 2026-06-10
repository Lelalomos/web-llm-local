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
        self.assertIn("Prefer concrete remembered facts", payload["messages"][0]["content"])

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

    def test_load_memory_text_uses_configured_prompt_context_limit(self):
        with _temporary_memory_paths():
            chat_memory.ensure_chat_memory_dirs()
            chat_memory.CHAT_MEMORY_FILE.write_text("a" * 5000, encoding="utf-8")

            memory_text = chat_memory.load_memory_text(1000)

        self.assertLessEqual(len(memory_text), 1000 + len("[Earlier memory truncated]\n\n"))
        self.assertIn("[Earlier memory truncated]", memory_text)

    def test_load_memory_text_selects_relevant_chunks_with_prompt_limit(self):
        memory_text = "\n\n".join(
            [
                "The user's favorite database is PostgreSQL.",
                "The user's name is Mos and the user is a programmer.",
                "The user likes stock market news.",
            ]
        )

        with _temporary_memory_paths():
            chat_memory.ensure_chat_memory_dirs()
            chat_memory.CHAT_MEMORY_FILE.write_text(memory_text, encoding="utf-8")

            selected = chat_memory.load_memory_text(120, "USER: hey i am programmer and i am mos what is your name?")

        self.assertIn("Mos", selected)
        self.assertIn("programmer", selected)
        self.assertNotIn("PostgreSQL", selected)

    def test_default_memory_prompt_window_keeps_concrete_name_before_later_unknown_notes(self):
        name_note = '## Important Facts\nUser full name is "Memory Window Test User."'
        unknown_note = "## Important Facts\nThe assistant did not know the user's name."
        filler = "x" * 9000

        with _temporary_memory_paths():
            chat_memory.ensure_chat_memory_dirs()
            chat_memory.CHAT_MEMORY_FILE.write_text(
                f"{name_note}\n\n{filler}\n\n{unknown_note}",
                encoding="utf-8",
            )

            memory_text = chat_memory.load_memory_text()

        self.assertIn("Memory Window Test User", memory_text)
        self.assertIn("did not know the user's name", memory_text)

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

    def test_append_summary_note_writes_only_summary_text(self):
        with _temporary_memory_paths():
            path = chat_memory.append_summary_note(
                "chat-1",
                "gemma4:e2b",
                "general",
                "## Important Facts\nThe user's name is Summary Only User.",
            )

            text = path.read_text(encoding="utf-8")

        self.assertIn("The user's name is Summary Only User.", text)
        self.assertNotIn("Session ID", text)
        self.assertNotIn("Model:", text)
        self.assertNotIn("Task Mode", text)

    def test_append_summary_note_appends_summary_text_without_metadata(self):
        with _temporary_memory_paths():
            chat_memory.append_summary_note("chat-1", "gemma4:e2b", "general", "## Important Facts\nFirst summary.")
            path = chat_memory.append_summary_note("chat-2", "gemma4:e2b", "general", "## Important Facts\nSecond summary.")

            text = path.read_text(encoding="utf-8")

        self.assertIn("First summary.", text)
        self.assertIn("Second summary.", text)
        self.assertNotIn("chat-1", text)
        self.assertNotIn("chat-2", text)

    def test_clear_chat_memory_removes_summary_active_and_archived_files(self):
        with _temporary_memory_paths():
            chat_memory.ensure_chat_memory_dirs()
            chat_memory.CHAT_MEMORY_FILE.write_text("memory", encoding="utf-8")
            (chat_memory.ACTIVE_SESSION_DIR / "active.json").write_text("{}", encoding="utf-8")
            (chat_memory.ARCHIVE_SESSION_DIR / "archived.json").write_text("{}", encoding="utf-8")
            (chat_memory.ARCHIVE_SESSION_DIR / "keep.txt").write_text("not a session", encoding="utf-8")

            result = chat_memory.clear_chat_memory()

            self.assertFalse(chat_memory.CHAT_MEMORY_FILE.exists())
            self.assertFalse((chat_memory.ACTIVE_SESSION_DIR / "active.json").exists())
            self.assertFalse((chat_memory.ARCHIVE_SESSION_DIR / "archived.json").exists())
            self.assertTrue((chat_memory.ARCHIVE_SESSION_DIR / "keep.txt").exists())

        self.assertTrue(result["summary_removed"])
        self.assertEqual(result["active_sessions_removed"], 1)
        self.assertEqual(result["archived_sessions_removed"], 1)

    def test_select_summary_rag_context_returns_relevant_memory_chunks(self):
        memory_text = "\n\n".join(
            [
                "The user's favorite database is PostgreSQL.",
                "The user's name is Relevant Memory User.",
                "The user likes short API examples.",
            ]
        )
        transcript = "USER: What is my name?\nASSISTANT: Your name is Relevant Memory User."

        selected = chat_memory.select_summary_rag_context(memory_text, transcript, 80)

        self.assertIn("Relevant Memory User", selected)
        self.assertNotIn("PostgreSQL", selected)

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

    def test_summarize_chat_session_uses_configured_summary_prompt(self):
        captured_payload = {}

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"message": {"content": "## Important Facts\nCustom prompt used."}}

        def fake_post(_url, json, timeout):
            captured_payload.update(json)
            return FakeResponse()

        with patch("chat_memory.requests.post", side_effect=fake_post):
            chat_memory.summarize_chat_session(
                "http://ollama:11434",
                "gemma4:e2b",
                [{"role": "user", "content": "hello"}],
                "general",
                "CUSTOM SUMMARY PROMPT TEXT",
            )

        self.assertEqual(captured_payload["messages"][0]["content"], "CUSTOM SUMMARY PROMPT TEXT")

    def test_summarize_chat_session_sends_existing_memory_rag_context(self):
        captured_payload = {}

        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"message": {"content": "## Important Facts\nThe user's name is RAG User."}}

        def fake_post(_url, json, timeout):
            captured_payload.update(json)
            return FakeResponse()

        with _temporary_memory_paths():
            chat_memory.ensure_chat_memory_dirs()
            chat_memory.CHAT_MEMORY_FILE.write_text(
                "The user's name is RAG User.\n\nThe user's favorite shell is bash.",
                encoding="utf-8",
            )

            with patch("chat_memory.requests.post", side_effect=fake_post):
                summary = chat_memory.summarize_chat_session(
                    "http://ollama:11434",
                    "gemma4:e2b",
                    [{"role": "user", "content": "My name is RAG User."}],
                    "general",
                )

        self.assertIn("RAG User", summary)
        user_prompt = captured_payload["messages"][-1]["content"]
        self.assertIn("Existing relevant long-term memory notes", user_prompt)
        self.assertIn("RAG User", user_prompt)
        self.assertIn("Recent finished chat transcript", user_prompt)
        self.assertNotIn("Task mode:", user_prompt)


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
