import unittest
from unittest.mock import patch

import requests

from intent_router import fallback_intent, fallback_task_mode, infer_chat_intent


class IntentRouterTests(unittest.TestCase):
    def test_fallback_routes_relationship_prompt_to_general(self):
        self.assertEqual(
            fallback_task_mode("if i fall in love with someone how should i do with who i love?", "code_writer"),
            "general",
        )

    def test_fallback_routes_code_prompt_to_code_writer(self):
        self.assertEqual(fallback_task_mode("i want to you write rust language for api?", "general"), "code_writer")

    def test_fallback_routes_review_prompt_to_code_reviewer(self):
        self.assertEqual(fallback_task_mode("please review this code for bugs", "general"), "code_reviewer")

    def test_fallback_intent_uses_search_policy(self):
        intent = fallback_intent("latest Gemma release news", "general")

        self.assertTrue(intent["web_search"])
        self.assertEqual(intent["source"], "fallback")
        self.assertIn("gemma", intent["search_query"])

    def test_infer_chat_intent_accepts_valid_model_json(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "message": {
                        "content": '{"task_mode":"general","web_search":true,"search_query":"latest local llm news"}'
                    }
                }

        with patch("intent_router.requests.post", return_value=FakeResponse()) as mocked_post:
            intent = infer_chat_intent(
                "http://ollama:11434",
                "what is the latest local llm news?",
                "general",
                {
                    "task_mode_interpreter_enabled": True,
                    "task_mode_interpreter_model": "qwen2.5:0.5b",
                    "task_mode_interpreter_timeout_seconds": 8,
                },
            )

        self.assertEqual(intent["task_mode"], "general")
        self.assertTrue(intent["web_search"])
        self.assertEqual(intent["search_query"], "latest local llm news")
        self.assertEqual(intent["source"], "model")
        self.assertEqual(mocked_post.call_args.kwargs["timeout"], 8)

    def test_infer_chat_intent_falls_back_on_model_error(self):
        with patch("intent_router.requests.post", side_effect=requests.exceptions.Timeout):
            intent = infer_chat_intent(
                "http://ollama:11434",
                "write python function to add numbers",
                "general",
                {
                    "task_mode_interpreter_enabled": True,
                    "task_mode_interpreter_model": "qwen2.5:0.5b",
                    "task_mode_interpreter_timeout_seconds": 1,
                },
            )

        self.assertEqual(intent["task_mode"], "code_writer")
        self.assertEqual(intent["source"], "fallback")

    def test_infer_chat_intent_suppresses_search_for_normal_code_prompt(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "message": {
                        "content": '{"task_mode":"code_writer","web_search":true,"search_query":"rust api example"}'
                    }
                }

        with patch("intent_router.requests.post", return_value=FakeResponse()):
            intent = infer_chat_intent(
                "http://ollama:11434",
                "i want to you write rust language for api?",
                "general",
                {
                    "task_mode_interpreter_enabled": True,
                    "task_mode_interpreter_model": "gemma2:2b",
                    "task_mode_interpreter_timeout_seconds": 30,
                },
            )

        self.assertEqual(intent["task_mode"], "code_writer")
        self.assertFalse(intent["web_search"])

    def test_infer_chat_intent_keeps_code_fallback_when_model_says_general(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "message": {
                        "content": '{"task_mode":"general","web_search":false,"search_query":"rust api"}'
                    }
                }

        with patch("intent_router.requests.post", return_value=FakeResponse()):
            intent = infer_chat_intent(
                "http://ollama:11434",
                "i test send write api with rust language into chat it can't write code",
                "general",
                {
                    "task_mode_interpreter_enabled": True,
                    "task_mode_interpreter_model": "gemma2:2b",
                    "task_mode_interpreter_timeout_seconds": 30,
                },
            )

        self.assertEqual(intent["task_mode"], "code_writer")
        self.assertFalse(intent["web_search"])
        self.assertEqual(intent["source"], "model")

    def test_infer_chat_intent_preserves_fallback_search_when_model_says_false(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "message": {
                        "content": '{"task_mode":"general","web_search":false,"search_query":"today what news of stock in us"}'
                    }
                }

        with patch("intent_router.requests.post", return_value=FakeResponse()):
            intent = infer_chat_intent(
                "http://ollama:11434",
                "today what news of stock in us",
                "general",
                {
                    "task_mode_interpreter_enabled": True,
                    "task_mode_interpreter_model": "gemma2:2b",
                    "task_mode_interpreter_timeout_seconds": 30,
                },
            )

        self.assertEqual(intent["task_mode"], "general")
        self.assertTrue(intent["web_search"])


if __name__ == "__main__":
    unittest.main()
