import unittest
from unittest.mock import patch
from pathlib import Path
import tempfile

import chat_memory
from app import (
    _apply_config_defaults,
    _apply_default_model,
    _apply_document_chat_defaults,
    _apply_thinking_defaults,
    _build_continuation_payload,
    _complete_non_stream_chat,
    _inject_direct_url_context,
    _inject_search_context,
    _merge_response_content,
    _normalize_model_name,
    _normalize_session_payload,
    _ollama_json_request,
    _search_requested,
    _search_status_line,
    _should_inject_memory_context,
    _stream_error_line,
    _should_continue_response,
    chat,
    delete_chat_memory,
    end_chat,
)


class AppSearchIntegrationTests(unittest.TestCase):
    def test_ended_chat_memory_is_injected_into_new_chat(self):
        captured_payloads = []
        captured_summary_payloads = []

        class FakeResponse:
            status_code = 200
            text = "{}"

            def __init__(self, content):
                self._content = content

            def json(self):
                return {"message": {"content": self._content}}

            def raise_for_status(self):
                return None

        def fake_ollama_chat(payload, stream=False):
            captured_payloads.append(payload)
            return FakeResponse("Okay, Test User.")

        def fake_summary_chat(url, json, timeout):
            captured_summary_payloads.append(json)
            return FakeResponse("## Important Facts\nThe user's name is Test User.")

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            with patch.multiple(
                chat_memory,
                CHAT_MEMORY_DIR=temp_root,
                ACTIVE_SESSION_DIR=temp_root / "active_sessions",
                ARCHIVE_SESSION_DIR=temp_root / "sessions",
                CHAT_MEMORY_FILE=temp_root / "summary_notes.md",
            ), patch("app.load_app_config", return_value={"default_web_search_mode": "off", "skill_markdown_enabled": False, "chat_summary_prompt": "APP CUSTOM SUMMARY PROMPT"}), patch("app._run_pending_summaries"), patch("app._post_ollama_chat", side_effect=fake_ollama_chat), patch(
                "chat_memory.requests.post",
                side_effect=fake_summary_chat,
            ):
                chat_memory.ensure_chat_memory_dirs()
                chat_memory.CHAT_MEMORY_FILE.write_text("## Important Facts\nThe user's name is Old Memory.", encoding="utf-8")

                first_response = chat(
                    {
                        "model": "gemma2:2b",
                        "stream": False,
                        "session_id": "name-memory",
                        "messages": [{"role": "user", "content": "My name is Test User."}],
                    }
                )

                self.assertEqual(first_response["message"]["content"], "Okay, Test User.")

                end_chat(
                    {
                        "model": "gemma2:2b",
                        "session_id": "name-memory",
                        "messages": [{"role": "user", "content": "My name is Test User."}],
                        "task_mode": "general",
                    }
                )

                second_response = chat(
                    {
                        "model": "gemma2:2b",
                        "stream": False,
                        "session_id": "new-chat",
                        "messages": [{"role": "user", "content": "What is my name?"}],
                    }
                )

        self.assertEqual(second_response["message"]["content"], "Okay, Test User.")
        self.assertEqual(captured_summary_payloads[0]["messages"][0]["content"], "APP CUSTOM SUMMARY PROMPT")
        summary_prompt = captured_summary_payloads[0]["messages"][-1]["content"]
        self.assertIn("Existing relevant long-term memory notes", summary_prompt)
        self.assertIn("Recent finished chat transcript", summary_prompt)
        self.assertIn("My name is Test User.", summary_prompt)
        self.assertIn("Okay, Test User.", summary_prompt)
        second_chat_payload = captured_payloads[-1]
        self.assertEqual(second_chat_payload["messages"][0]["role"], "system")
        self.assertIn("The user's name is Test User.", second_chat_payload["messages"][0]["content"])
        self.assertEqual(second_chat_payload["messages"][-1]["content"], "What is my name?")

    def test_inject_search_context_adds_system_message(self):
        payload = {"messages": [{"role": "user", "content": "latest stock news"}]}

        with patch("app.execute_web_search", return_value=("Source: Reuters\nURL: https://reuters.com", [{"href": "https://reuters.com"}])), patch(
            "app.enhance_search_context",
            side_effect=lambda _ollama_url, _query, raw_context, _results, _app_config: (raw_context, False, ""),
        ):
            search_used = _inject_search_context(payload, True, {"web_search_context_max_chars": 6000})

        self.assertTrue(search_used)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("Use the following Web Search results", payload["messages"][0]["content"])

    def test_inject_search_context_appends_existing_system_message(self):
        payload = {
            "messages": [
                {"role": "system", "content": "base system"},
                {"role": "user", "content": "latest stock news"},
            ]
        }

        with patch("app.execute_web_search", return_value=("Source: Reuters\nURL: https://reuters.com", [{"href": "https://reuters.com"}])), patch(
            "app.enhance_search_context",
            side_effect=lambda _ollama_url, _query, raw_context, _results, _app_config: (raw_context, False, ""),
        ):
            search_used = _inject_search_context(payload, True, {"web_search_context_max_chars": 6000})

        self.assertTrue(search_used)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("base system", payload["messages"][0]["content"])
        self.assertIn("Use the following Web Search results", payload["messages"][0]["content"])

    def test_inject_search_context_skips_when_no_results(self):
        payload = {"messages": [{"role": "user", "content": "latest stock news"}]}

        with patch("app.execute_web_search", return_value=("No web search results found.", [])), patch(
            "app.enhance_search_context",
            side_effect=lambda _ollama_url, _query, raw_context, _results, _app_config: (raw_context, False, ""),
        ):
            search_used = _inject_search_context(payload, True, {"web_search_context_max_chars": 6000})

        self.assertFalse(search_used)
        self.assertEqual(len(payload["messages"]), 1)

    def test_inject_search_context_uses_enhanced_context(self):
        payload = {"messages": [{"role": "user", "content": "latest stock news"}]}

        with patch("app.execute_web_search", return_value=("raw context", [{"href": "https://reuters.com"}])), patch(
            "app.enhance_search_context",
            return_value=("Small-model Search Brief:\nbrief\n\nRaw Search Evidence:\nraw context", True, "gemma2:2b"),
        ):
            search_used = _inject_search_context(payload, True, {"web_search_context_max_chars": 6000})

        self.assertTrue(search_used)
        self.assertIn("Small-model Search Brief", payload["messages"][0]["content"])

    def test_inject_direct_url_context_adds_exact_page_context(self):
        payload = {"messages": [{"role": "user", "content": "Summarize https://distill.pub/2021/gnn-intro/"}]}

        with patch("app.build_direct_url_context", return_value=("Website: https://distill.pub/2021/gnn-intro/\nExtracted page text:\nGNN intro", ["https://distill.pub/2021/gnn-intro/"])):
            injected = _inject_direct_url_context(payload, {"web_search_context_max_chars": 6000})

        self.assertTrue(injected)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("Website Context", payload["messages"][0]["content"])
        self.assertIn("GNN intro", payload["messages"][0]["content"])

    def test_search_status_line_contains_exact_flag(self):
        self.assertEqual(_search_status_line(True), '{"type": "search_status", "search_used": true}\n')
        self.assertEqual(_search_status_line(False), '{"type": "search_status", "search_used": false}\n')

    def test_stream_error_line_contains_message(self):
        self.assertEqual(_stream_error_line("timeout"), '{"type": "stream_error", "message": "timeout"}\n')

    def test_search_requested_uses_config_default_mode(self):
        payload = {"messages": [{"role": "user", "content": "explain gravity"}]}
        self.assertTrue(_search_requested(dict(payload), {"default_web_search_mode": "on"}))
        self.assertFalse(_search_requested(dict(payload), {"default_web_search_mode": "off"}))

    def test_search_requested_skips_auto_search_for_code_tasks(self):
        payload = {"messages": [{"role": "user", "content": "you write rust for search engine?"}]}

        self.assertFalse(_search_requested(dict(payload), {"default_web_search_mode": "auto"}, "code_writer"))

    def test_search_requested_skips_search_when_direct_url_context_exists(self):
        payload = {"messages": [{"role": "user", "content": "summarize https://example.com"}]}

        self.assertFalse(_search_requested(dict(payload), {"default_web_search_mode": "auto"}, "general", True))
        self.assertTrue(_search_requested(dict(payload, web_search_mode="on"), {"default_web_search_mode": "auto"}, "general", True))

    def test_search_requested_skips_auto_search_for_document_prompt(self):
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": 'Context from uploaded file "report.pdf":\n\n--- START OF FILE CONTENT ---\nlatest stock news in this report\n--- END OF FILE CONTENT ---\n\nUse the file content above to answer this prompt: Summarize this document.',
                }
            ]
        }

        with patch("app.infer_chat_intent") as mocked_infer:
            self.assertFalse(_search_requested(dict(payload), {"default_web_search_mode": "auto"}, "general"))

        self.assertFalse(mocked_infer.called)
        self.assertTrue(_search_requested(dict(payload, web_search_mode="on"), {"default_web_search_mode": "auto"}, "general"))

    def test_search_requested_uses_interpreter_for_auto_search(self):
        payload = {"messages": [{"role": "user", "content": "what changed in latest gemma?"}]}

        with patch(
            "app.infer_chat_intent",
            return_value={
                "task_mode": "general",
                "web_search": True,
                "search_query": "latest gemma news",
                "source": "model",
            },
        ):
            self.assertTrue(_search_requested(payload, {"default_web_search_mode": "auto"}, "general"))

        self.assertEqual(payload["_web_search_query"], "latest gemma news")

    def test_apply_default_model_uses_config_when_missing(self):
        payload = {"messages": [{"role": "user", "content": "hello"}]}
        _apply_default_model(payload, {"default_model": "gemma4:e2b"})
        self.assertEqual(payload["model"], "gemma4:e2b")

    def test_apply_config_defaults_sets_system_prompt_and_options(self):
        payload = {"messages": [{"role": "user", "content": "hello"}]}
        _apply_config_defaults(
            payload,
            {
                "default_system_prompt": "Follow config",
                "default_options": {"num_predict": 1200},
            },
        )

        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("Follow config", payload["messages"][0]["content"])
        self.assertEqual(payload["options"]["num_predict"], 1200)

    def test_document_prompt_disables_thinking_by_default(self):
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": 'Context from uploaded file "report.pdf":\n\n--- START OF FILE CONTENT ---\nhello\n--- END OF FILE CONTENT ---\n\nUse the file content above to answer this prompt: Summarize this document.',
                }
            ]
        }

        _apply_document_chat_defaults(payload)

        self.assertFalse(payload["think"])

    def test_explicit_think_flag_is_preserved(self):
        payload = {
            "think": True,
            "messages": [
                {
                    "role": "user",
                    "content": 'Context from uploaded file "report.pdf":\n\n--- START OF FILE CONTENT ---\nhello\n--- END OF FILE CONTENT ---\n\nUse the file content above to answer this prompt: Summarize this document.',
                }
            ]
        }

        _apply_document_chat_defaults(payload)

        self.assertTrue(payload["think"])

    def test_thinking_is_disabled_by_default_for_all_chats(self):
        payload = {"messages": [{"role": "user", "content": "hello"}]}

        _apply_thinking_defaults(payload)

        self.assertFalse(payload["think"])

    def test_document_chat_skips_memory_by_config_and_skips_summary_and_skill_context(self):
        payload = {
            "model": "gemma2:2b",
            "stream": False,
            "session_id": "doc-session",
            "messages": [
                {
                    "role": "user",
                    "content": 'Context from uploaded file "report.pdf":\n\n--- START OF FILE CONTENT ---\nhello\n--- END OF FILE CONTENT ---\n\nUse the file content above to answer this prompt: Summarize this document.',
                }
            ],
        }

        with patch("app.load_app_config", return_value={"default_web_search_mode": "auto", "skill_markdown_enabled": True, "memory_used": {"upload_file": False}}), patch("app._run_pending_summaries") as summaries_mock, patch("app.inject_memory_context") as memory_mock, patch("app.inject_skill_context") as skill_mock, patch("app._complete_non_stream_chat", return_value={"message": {"content": "summary"}}), patch("app._persist_completed_chat"):
            response = chat(payload)

        self.assertEqual(response["message"]["content"], "summary")
        summaries_mock.assert_not_called()
        memory_mock.assert_not_called()
        skill_mock.assert_not_called()

    def test_document_chat_uses_memory_when_upload_file_config_enabled(self):
        payload = {
            "model": "gemma2:2b",
            "stream": False,
            "session_id": "doc-session",
            "messages": [
                {
                    "role": "user",
                    "content": 'Context from uploaded file "report.pdf":\n\n--- START OF FILE CONTENT ---\nhello\n--- END OF FILE CONTENT ---\n\nUse the file content above to answer this prompt: Summarize this document.',
                }
            ],
        }

        with patch("app.load_app_config", return_value={"default_web_search_mode": "auto", "skill_markdown_enabled": False, "memory_used": {"upload_file": True}}), patch("app._run_pending_summaries"), patch("app.inject_memory_context") as memory_mock, patch("app._complete_non_stream_chat", return_value={"message": {"content": "summary"}}), patch("app._persist_completed_chat"):
            response = chat(payload)

        self.assertEqual(response["message"]["content"], "summary")
        memory_mock.assert_called_once()

    def test_general_chat_uses_memory_context(self):
        payload = {
            "model": "gemma2:2b",
            "stream": False,
            "session_id": "general-session",
            "messages": [{"role": "user", "content": "remember my name?"}],
        }

        with patch("app.load_app_config", return_value={"default_web_search_mode": "off", "skill_markdown_enabled": False, "memory_used": {"general": True}}), patch("app._run_pending_summaries"), patch("app.inject_memory_context") as memory_mock, patch("app._complete_non_stream_chat", return_value={"message": {"content": "answer"}}), patch("app._persist_completed_chat"):
            response = chat(payload)

        self.assertEqual(response["message"]["content"], "answer")
        memory_mock.assert_called_once()

    def test_code_writer_chat_uses_memory_when_config_enabled(self):
        payload = {
            "model": "gemma2:2b",
            "stream": False,
            "session_id": "code-session",
            "task_mode": "code_writer",
            "web_search_mode": "off",
            "messages": [{"role": "user", "content": "write rust api client code"}],
        }

        with patch("app.load_app_config", return_value={"default_web_search_mode": "off", "skill_markdown_enabled": False, "memory_used": {"code_writer": True}}), patch("app._run_pending_summaries"), patch("app.inject_memory_context") as memory_mock, patch("app._complete_non_stream_chat", return_value={"message": {"content": "code"}}), patch("app._persist_completed_chat"):
            response = chat(payload)

        self.assertEqual(response["message"]["content"], "code")
        memory_mock.assert_called_once()

    def test_code_writer_chat_skips_memory_when_config_disabled(self):
        payload = {
            "model": "gemma2:2b",
            "stream": False,
            "session_id": "code-session",
            "task_mode": "code_writer",
            "web_search_mode": "off",
            "messages": [{"role": "user", "content": "write rust api client code"}],
        }

        with patch("app.load_app_config", return_value={"default_web_search_mode": "off", "skill_markdown_enabled": False, "memory_used": {"code_writer": False}}), patch("app._run_pending_summaries"), patch("app.inject_memory_context") as memory_mock, patch("app._complete_non_stream_chat", return_value={"message": {"content": "code"}}), patch("app._persist_completed_chat"):
            response = chat(payload)

        self.assertEqual(response["message"]["content"], "code")
        memory_mock.assert_not_called()

    def test_web_search_chat_skips_memory_context(self):
        payload = {
            "model": "gemma2:2b",
            "stream": False,
            "session_id": "search-session",
            "web_search_mode": "on",
            "messages": [{"role": "user", "content": "get news stock data in US"}],
        }

        with patch("app.load_app_config", return_value={"default_web_search_mode": "auto", "skill_markdown_enabled": False, "memory_used": {"general": True}}), patch("app._run_pending_summaries"), patch("app.inject_memory_context") as memory_mock, patch("app._inject_search_context", return_value=True), patch("app._complete_non_stream_chat", return_value={"message": {"content": "stock news"}}), patch("app._persist_completed_chat"):
            response = chat(payload)

        self.assertEqual(response["message"]["content"], "stock news")
        memory_mock.assert_not_called()

    def test_memory_context_policy(self):
        config = {"memory_used": {"general": True, "code_writer": True, "code_reviewer": True, "code_editor": False, "bug_fixer": False, "upload_file": False}}

        self.assertTrue(_should_inject_memory_context("general", False, config))
        self.assertTrue(_should_inject_memory_context("code_writer", False, config))
        self.assertTrue(_should_inject_memory_context("code_reviewer", False, config))
        self.assertFalse(_should_inject_memory_context("code_editor", False, config))
        self.assertFalse(_should_inject_memory_context("bug_fixer", False, config))
        self.assertFalse(_should_inject_memory_context("general", True, config))
        self.assertFalse(_should_inject_memory_context("general", False, config, True))
        self.assertTrue(_should_inject_memory_context("general", False, {"memory_used": {"upload_file": True}}, True))

    def test_chat_reads_all_skill_files_before_answer(self):
        captured_payloads = []

        class FakeResponse:
            status_code = 200
            text = "{}"

            def json(self):
                return {"message": {"content": "answer"}}

        def fake_ollama_chat(payload, stream=False):
            captured_payloads.append(payload)
            return FakeResponse()

        with tempfile.TemporaryDirectory() as temp_dir:
            skill_dir = Path(temp_dir) / "skill"
            nested_dir = skill_dir / "nested"
            nested_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "a.md").write_text("Always mention Alpha skill.", encoding="utf-8")
            (nested_dir / "b.md").write_text("Always mention Beta skill.", encoding="utf-8")

            with patch("skill_loader.SKILL_DIR", skill_dir), patch("app.load_app_config", return_value={"default_web_search_mode": "off", "skill_markdown_enabled": True, "skill_prompt_max_chars": 12000}), patch("app._run_pending_summaries"), patch("app.inject_memory_context"), patch("app._post_ollama_chat", side_effect=fake_ollama_chat), patch("app._persist_completed_chat"):
                response = chat(
                    {
                        "model": "gemma2:2b",
                        "stream": False,
                        "session_id": "skill-session",
                        "messages": [{"role": "user", "content": "hello"}],
                    }
                )

        self.assertEqual(response["message"]["content"], "answer")
        model_messages = captured_payloads[0]["messages"]
        self.assertEqual(model_messages[0]["role"], "system")
        self.assertIn("## Skill File: a.md", model_messages[0]["content"])
        self.assertIn("Always mention Alpha skill.", model_messages[0]["content"])
        self.assertIn("## Skill File: nested/b.md", model_messages[0]["content"])
        self.assertIn("Always mention Beta skill.", model_messages[0]["content"])
        self.assertEqual(model_messages[-1]["content"], "hello")

    def test_delete_chat_memory_endpoint_clears_saved_memory(self):
        with patch("app.clear_chat_memory", return_value={"summary_removed": True, "active_sessions_removed": 2, "archived_sessions_removed": 3}):
            response = delete_chat_memory()

        self.assertEqual(response["status"], "cleared")
        self.assertTrue(response["summary_removed"])
        self.assertEqual(response["active_sessions_removed"], 2)
        self.assertEqual(response["archived_sessions_removed"], 3)

    def test_normalize_session_payload_requires_model_and_messages(self):
        with self.assertRaisesRegex(Exception, "model is required"):
            _normalize_session_payload({"messages": [{"role": "user", "content": "hello"}]})

        with self.assertRaisesRegex(Exception, "messages are required"):
            _normalize_session_payload({"model": "gemma4:e2b", "messages": []})

    def test_normalize_session_payload_returns_values(self):
        model, session_id, messages, task_mode = _normalize_session_payload(
            {
                "model": "gemma4:e2b",
                "session_id": "chat-123",
                "messages": [{"role": "user", "content": "hello"}],
                "task_mode": "general",
            }
        )

        self.assertEqual(model, "gemma4:e2b")
        self.assertEqual(session_id, "chat-123")
        self.assertEqual(task_mode, "general")
        self.assertEqual(messages[0]["content"], "hello")

    def test_normalize_model_name_rejects_invalid_values(self):
        self.assertEqual(_normalize_model_name({"model": "qwen2.5:0.5b"}), "qwen2.5:0.5b")

        with self.assertRaisesRegex(Exception, "model is required"):
            _normalize_model_name({})

        with self.assertRaisesRegex(Exception, "invalid model name"):
            _normalize_model_name({"model": "bad model name"})

    def test_ollama_json_request_returns_json_and_raises_on_error(self):
        class FakeResponse:
            def __init__(self, status_code, body, text=None):
                self.status_code = status_code
                self._body = body
                self.text = str(body) if text is None else text

            def json(self):
                return self._body

        with patch("app.requests.request", return_value=FakeResponse(200, {"status": "success"})) as mocked_request:
            result = _ollama_json_request("/api/pull", {"model": "qwen2.5:0.5b"})
        self.assertEqual(result["status"], "success")
        self.assertEqual(mocked_request.call_args.args[0], "POST")

        with patch("app.requests.request", return_value=FakeResponse(200, {}, "")):
            result = _ollama_json_request("/api/delete", {"model": "qwen2.5:0.5b"}, method="DELETE")
        self.assertEqual(result["status"], "success")

        with patch("app.requests.request", return_value=FakeResponse(500, {"error": "boom"}, "boom")):
            with self.assertRaisesRegex(Exception, "boom"):
                _ollama_json_request("/api/delete", {"model": "qwen2.5:0.5b"})

    def test_should_continue_response_for_any_task_mode(self):
        response = {"done_reason": "length", "message": {"content": "print('hi')"}}

        self.assertTrue(_should_continue_response("code_writer", False, response))
        self.assertTrue(_should_continue_response("general", True, response))
        self.assertTrue(_should_continue_response("general", False, response))
        self.assertFalse(_should_continue_response("general", False, {"done_reason": "stop", "message": {"content": "done"}}))

    def test_should_continue_response_uses_streamed_content_when_final_chunk_is_empty(self):
        response = {"done_reason": "length", "message": {"content": ""}}

        self.assertTrue(_should_continue_response("general", False, response, "partial streamed answer"))
        self.assertFalse(_should_continue_response("general", False, response, ""))

    def test_build_continuation_payload_appends_messages(self):
        payload = {"messages": [{"role": "user", "content": "write code"}], "stream": True}

        continuation_payload = _build_continuation_payload(payload, "partial code")

        self.assertEqual(continuation_payload["messages"][-2]["role"], "assistant")
        self.assertEqual(continuation_payload["messages"][-1]["role"], "user")
        self.assertFalse(continuation_payload["stream"])

    def test_merge_response_content_stitches_outputs(self):
        merged = _merge_response_content(
            {"message": {"content": "part one"}, "done_reason": "length", "eval_count": 10, "eval_duration": 20, "total_duration": 30},
            {"message": {"content": "part two"}, "done_reason": "stop", "eval_count": 5, "eval_duration": 7, "total_duration": 9},
        )

        self.assertIn("part one", merged["message"]["content"])
        self.assertIn("part two", merged["message"]["content"])
        self.assertEqual(merged["done_reason"], "stop")
        self.assertEqual(merged["eval_count"], 15)

    def test_complete_non_stream_chat_continues_once_for_general_mode(self):
        payload = {"messages": [{"role": "user", "content": "write a long answer"}], "stream": False}

        class FakeResponse:
            def __init__(self, status_code, body):
                self.status_code = status_code
                self._body = body
                self.text = str(body)

            def json(self):
                return self._body

        responses = [
            FakeResponse(200, {"message": {"content": "part one"}, "done_reason": "length", "eval_count": 3, "eval_duration": 4, "total_duration": 5}),
            FakeResponse(200, {"message": {"content": "part two"}, "done_reason": "stop", "eval_count": 6, "eval_duration": 7, "total_duration": 8}),
        ]

        with patch("app._post_ollama_chat", side_effect=responses):
            merged = _complete_non_stream_chat(payload, "general", False, 2)

        self.assertIn("part one", merged["message"]["content"])
        self.assertIn("part two", merged["message"]["content"])
        self.assertEqual(merged["done_reason"], "stop")

    def test_complete_non_stream_chat_continues_for_search_responses(self):
        payload = {"messages": [{"role": "user", "content": "latest stock news"}], "stream": False}

        class FakeResponse:
            def __init__(self, status_code, body):
                self.status_code = status_code
                self._body = body
                self.text = str(body)

            def json(self):
                return self._body

        responses = [
            FakeResponse(200, {"message": {"content": "part one"}, "done_reason": "length", "eval_count": 1, "eval_duration": 1, "total_duration": 1}),
            FakeResponse(200, {"message": {"content": "part two"}, "done_reason": "stop", "eval_count": 1, "eval_duration": 1, "total_duration": 1}),
        ]

        with patch("app._post_ollama_chat", side_effect=responses):
            merged = _complete_non_stream_chat(payload, "general", True, 2)

        self.assertIn("part one", merged["message"]["content"])
        self.assertIn("part two", merged["message"]["content"])


class AppCorsTests(unittest.TestCase):
    def test_cors_middleware_is_enabled(self):
        from app import app
        from fastapi.middleware.cors import CORSMiddleware
        cors_middleware_found = False
        for middleware in app.user_middleware:
            if middleware.cls == CORSMiddleware:
                cors_middleware_found = True
                break
        self.assertTrue(cors_middleware_found, "CORSMiddleware is not registered on the FastAPI app")


if __name__ == "__main__":
    unittest.main()
