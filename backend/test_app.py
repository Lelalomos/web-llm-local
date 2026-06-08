import unittest
from unittest.mock import patch

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
    _stream_error_line,
    _should_continue_response,
    chat,
)


class AppSearchIntegrationTests(unittest.TestCase):
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

    def test_document_chat_skips_memory_summary_and_skill_context(self):
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

        with patch("app.load_app_config", return_value={"default_web_search_mode": "auto", "skill_markdown_enabled": True}), patch("app._run_pending_summaries") as summaries_mock, patch("app.inject_memory_context") as memory_mock, patch("app.inject_skill_context") as skill_mock, patch("app._complete_non_stream_chat", return_value={"message": {"content": "summary"}}), patch("app._persist_completed_chat"):
            response = chat(payload)

        self.assertEqual(response["message"]["content"], "summary")
        summaries_mock.assert_not_called()
        memory_mock.assert_not_called()
        skill_mock.assert_not_called()

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
