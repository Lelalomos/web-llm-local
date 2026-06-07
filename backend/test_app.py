import unittest
from unittest.mock import patch

from app import (
    _apply_document_chat_defaults,
    _build_continuation_payload,
    _complete_non_stream_chat,
    _inject_search_context,
    _merge_response_content,
    _normalize_model_name,
    _normalize_session_payload,
    _ollama_json_request,
    _search_status_line,
    _should_continue_coding_response,
)


class AppSearchIntegrationTests(unittest.TestCase):
    def test_inject_search_context_adds_system_message(self):
        payload = {"messages": [{"role": "user", "content": "latest stock news"}]}

        with patch("app.execute_web_search", return_value=("Source: Reuters\nURL: https://reuters.com", [{"href": "https://reuters.com"}])):
            search_used = _inject_search_context(payload, True)

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

        with patch("app.execute_web_search", return_value=("Source: Reuters\nURL: https://reuters.com", [{"href": "https://reuters.com"}])):
            search_used = _inject_search_context(payload, True)

        self.assertTrue(search_used)
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertIn("base system", payload["messages"][0]["content"])
        self.assertIn("Use the following Web Search results", payload["messages"][0]["content"])

    def test_inject_search_context_skips_when_no_results(self):
        payload = {"messages": [{"role": "user", "content": "latest stock news"}]}

        with patch("app.execute_web_search", return_value=("No web search results found.", [])):
            search_used = _inject_search_context(payload, True)

        self.assertFalse(search_used)
        self.assertEqual(len(payload["messages"]), 1)

    def test_search_status_line_contains_exact_flag(self):
        self.assertEqual(_search_status_line(True), '{"type": "search_status", "search_used": true}\n')
        self.assertEqual(_search_status_line(False), '{"type": "search_status", "search_used": false}\n')

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

    def test_should_continue_coding_response_only_for_coding_modes(self):
        response = {"done_reason": "length", "message": {"content": "print('hi')"}}

        self.assertTrue(_should_continue_coding_response("code_writer", response))
        self.assertFalse(_should_continue_coding_response("general", response))

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

    def test_complete_non_stream_chat_continues_once_for_coding_mode(self):
        payload = {"messages": [{"role": "user", "content": "write code"}], "stream": False}

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
            merged = _complete_non_stream_chat(payload, "code_writer")

        self.assertIn("part one", merged["message"]["content"])
        self.assertIn("part two", merged["message"]["content"])
        self.assertEqual(merged["done_reason"], "stop")


if __name__ == "__main__":
    unittest.main()
