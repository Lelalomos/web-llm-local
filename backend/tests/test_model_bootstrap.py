import unittest
from unittest.mock import patch

from model_bootstrap import ensure_default_model_available, extract_model_names, should_pull_default_model


class ModelBootstrapTests(unittest.TestCase):
    def test_extract_model_names(self):
        self.assertEqual(
            extract_model_names({"models": [{"name": "gemma2:2b"}, {"name": "qwen2.5:0.5b"}]}),
            ["gemma2:2b", "qwen2.5:0.5b"],
        )
        self.assertEqual(extract_model_names({"models": []}), [])

    def test_should_pull_default_model(self):
        self.assertTrue(should_pull_default_model({"models": []}))
        self.assertFalse(should_pull_default_model({"models": [{"name": "gemma2:2b"}]}))

    def test_ensure_default_model_available_skips_when_models_exist(self):
        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        with patch("model_bootstrap.requests.get", return_value=FakeResponse({"models": [{"name": "gemma2:2b"}]})) as mocked_get, patch("model_bootstrap.requests.post") as mocked_post:
            result = ensure_default_model_available("http://ollama:11434", "gemma2:2b")

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(mocked_get.call_count, 1)
        self.assertEqual(mocked_post.call_count, 0)

    def test_ensure_default_model_available_pulls_when_empty(self):
        class FakeGetResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {"models": []}

        class FakePostResponse:
            text = ""

            def raise_for_status(self):
                return None

            def json(self):
                return {"status": "success"}

        with patch("model_bootstrap.requests.get", return_value=FakeGetResponse()), patch("model_bootstrap.requests.post", return_value=FakePostResponse()) as mocked_post:
            result = ensure_default_model_available("http://ollama:11434", "gemma2:2b")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["model"], "gemma2:2b")
        self.assertEqual(mocked_post.call_count, 1)


if __name__ == "__main__":
    unittest.main()
