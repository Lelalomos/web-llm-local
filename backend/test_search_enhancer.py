import unittest
from unittest.mock import patch

import requests

from search_enhancer import _candidate_models, enhance_search_context


class SearchEnhancerTests(unittest.TestCase):
    def test_candidate_models_dedupes_and_falls_back(self):
        self.assertEqual(
            _candidate_models(
                {
                    "search_context_enhancer_model": "qwen2.5:0.5b",
                    "task_mode_interpreter_model": "qwen2.5:0.5b",
                }
            ),
            ["qwen2.5:0.5b", "gemma2:2b"],
        )

    def test_enhance_search_context_returns_combined_context(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"message": {"content": "1. Answer Focus: answer current news\n2. Key Facts: fact"}}

        with patch("search_enhancer.requests.post", return_value=FakeResponse()) as mocked_post:
            context, enhanced, model = enhance_search_context(
                "http://ollama:11434",
                "latest gemma news",
                "Source: Example\nURL: https://example.com\nSnippet: Gemma news",
                [{"title": "Example", "href": "https://example.com", "body": "Gemma news"}],
                {
                    "search_context_enhancer_enabled": True,
                    "search_context_enhancer_model": "qwen2.5:0.5b",
                    "search_context_enhancer_timeout_seconds": 45,
                    "search_context_enhancer_max_chars": 6000,
                },
            )

        self.assertTrue(enhanced)
        self.assertEqual(model, "qwen2.5:0.5b")
        self.assertIn("Small-model Search Brief", context)
        self.assertIn("Raw Search Evidence", context)
        self.assertEqual(mocked_post.call_args.kwargs["timeout"], 45)

    def test_enhance_search_context_tries_fallback_model_on_error(self):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"message": {"content": "brief"}}

        with patch(
            "search_enhancer.requests.post",
            side_effect=[requests.exceptions.HTTPError("missing model"), FakeResponse()],
        ):
            context, enhanced, model = enhance_search_context(
                "http://ollama:11434",
                "latest gemma news",
                "raw context",
                [],
                {
                    "search_context_enhancer_enabled": True,
                    "search_context_enhancer_model": "qwen2.5:0.5b",
                    "task_mode_interpreter_model": "gemma2:2b",
                    "search_context_enhancer_timeout_seconds": 45,
                    "search_context_enhancer_max_chars": 6000,
                },
            )

        self.assertTrue(enhanced)
        self.assertEqual(model, "gemma2:2b")
        self.assertIn("brief", context)

    def test_enhance_search_context_returns_raw_when_disabled(self):
        context, enhanced, model = enhance_search_context(
            "http://ollama:11434",
            "query",
            "raw context",
            [],
            {"search_context_enhancer_enabled": False},
        )

        self.assertEqual(context, "raw context")
        self.assertFalse(enhanced)
        self.assertEqual(model, "")


if __name__ == "__main__":
    unittest.main()
