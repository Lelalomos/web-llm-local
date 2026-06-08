import unittest
from unittest.mock import patch

from search_service import (
    build_direct_url_context,
    execute_web_search,
    extract_http_urls,
    index_meilisearch_results,
    is_safe_public_url,
    search_meilisearch,
    search_searxng,
)


class SearchServiceUrlContextTests(unittest.TestCase):
    def test_extract_http_urls_strips_trailing_punctuation(self):
        self.assertEqual(
            extract_http_urls("Summarize https://distill.pub/2021/gnn-intro/."),
            ["https://distill.pub/2021/gnn-intro/"],
        )

    def test_rejects_local_and_private_urls(self):
        self.assertFalse(is_safe_public_url("http://localhost:8000/admin"))
        self.assertFalse(is_safe_public_url("http://127.0.0.1:8000/admin"))
        self.assertFalse(is_safe_public_url("http://10.0.0.1/admin"))

    def test_accepts_public_url_when_dns_resolves_publicly(self):
        with patch("search_service.socket.getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 443))]):
            self.assertTrue(is_safe_public_url("https://example.com/page"))

    def test_build_direct_url_context_uses_exact_url_content(self):
        with patch("search_service.scrape_url_content", return_value="Graph neural networks pass messages over graph edges."):
            context, urls = build_direct_url_context("Analyze https://distill.pub/2021/gnn-intro/", 1000)

        self.assertEqual(urls, ["https://distill.pub/2021/gnn-intro/"])
        self.assertIn("Website: https://distill.pub/2021/gnn-intro/", context)
        self.assertIn("Graph neural networks", context)

    def test_search_searxng_parses_json_results(self):
        class FakeResponse:
            status_code = 200

            def json(self):
                return {
                    "results": [
                        {
                            "title": "Gemma news",
                            "url": "https://example.com/gemma",
                            "content": "Gemma release details",
                        }
                    ]
                }

        with patch("search_service.requests.get", return_value=FakeResponse()) as mocked_get:
            results = search_searxng("latest gemma", "http://searxng:8080", 8)

        self.assertEqual(results[0]["title"], "Gemma news")
        self.assertEqual(results[0]["href"], "https://example.com/gemma")
        self.assertEqual(results[0]["provider"], "searxng")
        self.assertEqual(mocked_get.call_args.kwargs["params"]["format"], "json")

    def test_search_meilisearch_parses_hits(self):
        class FakeResponse:
            status_code = 200

            def json(self):
                return {
                    "hits": [
                        {
                            "title": "Cached Gemma",
                            "href": "https://example.com/cached",
                            "body": "cached body",
                        }
                    ]
                }

        with patch("search_service.requests.post", return_value=FakeResponse()):
            results = search_meilisearch(
                "gemma",
                {
                    "meilisearch_enabled": True,
                    "meilisearch_url": "http://meilisearch:7700",
                    "meilisearch_index": "web_search_results",
                    "meilisearch_timeout_seconds": 3,
                },
            )

        self.assertEqual(results[0]["provider"], "meilisearch")
        self.assertEqual(results[0]["href"], "https://example.com/cached")

    def test_index_meilisearch_results_posts_documents(self):
        class FakeResponse:
            status_code = 202

        with patch("search_service.requests.post", return_value=FakeResponse()) as mocked_post:
            indexed = index_meilisearch_results(
                "gemma",
                [{"title": "Gemma", "href": "https://example.com/gemma", "body": "body"}],
                {
                    "meilisearch_enabled": True,
                    "meilisearch_url": "http://meilisearch:7700",
                    "meilisearch_index": "web_search_results",
                    "meilisearch_timeout_seconds": 3,
                },
            )

        self.assertTrue(indexed)
        self.assertEqual(mocked_post.call_args.kwargs["params"]["primaryKey"], "id")
        self.assertEqual(mocked_post.call_args.kwargs["json"][0]["href"], "https://example.com/gemma")

    def test_execute_web_search_auto_combines_searxng_legacy_and_cache(self):
        with patch(
            "search_service.search_meilisearch",
            return_value=[{"title": "Cached", "href": "https://example.com/cached", "body": "cached"}],
        ), patch(
            "search_service.search_searxng",
            return_value=[{"title": "Live", "href": "https://example.com/live", "body": "live"}],
        ) as mocked_searxng, patch("search_service.scrape_url_content", return_value=""), patch(
            "search_service._legacy_web_search",
            return_value=[{"title": "Legacy", "href": "https://example.com/legacy", "body": "legacy"}],
        ) as mocked_legacy, patch(
            "search_service.index_meilisearch_results",
            return_value=True,
        ):
            context, results = execute_web_search(
                "latest gemma",
                {
                    "search_provider": "auto",
                    "searxng_enabled": True,
                    "searxng_url": "http://searxng:8080",
                    "searxng_timeout_seconds": 8,
                    "meilisearch_enabled": True,
                },
            )

        self.assertTrue(mocked_searxng.called)
        self.assertTrue(mocked_legacy.called)
        self.assertIn("Live", context)
        self.assertTrue(any(result["href"] == "https://example.com/legacy" for result in results))
        self.assertTrue(any(result["href"] == "https://example.com/cached" for result in results))

    def test_execute_web_search_searxng_mode_skips_legacy(self):
        with patch("search_service.search_meilisearch", return_value=[]), patch(
            "search_service.search_searxng",
            return_value=[{"title": "Live", "href": "https://example.com/live", "body": "live"}],
        ) as mocked_searxng, patch(
            "search_service._legacy_web_search",
            return_value=[{"title": "Legacy", "href": "https://example.com/legacy", "body": "legacy"}],
        ) as mocked_legacy, patch("search_service.scrape_url_content", return_value=""), patch(
            "search_service.index_meilisearch_results",
            return_value=True,
        ):
            context, _ = execute_web_search(
                "latest gemma",
                {
                    "search_provider": "searxng",
                    "searxng_enabled": True,
                    "meilisearch_enabled": True,
                },
            )

        self.assertTrue(mocked_searxng.called)
        self.assertFalse(mocked_legacy.called)
        self.assertIn("Live", context)

    def test_execute_web_search_legacy_mode_skips_searxng(self):
        with patch("search_service.search_meilisearch", return_value=[]), patch(
            "search_service.search_searxng",
            return_value=[{"title": "Live", "href": "https://example.com/live", "body": "live"}],
        ) as mocked_searxng, patch(
            "search_service._legacy_web_search",
            return_value=[{"title": "Legacy", "href": "https://example.com/legacy", "body": "legacy"}],
        ) as mocked_legacy, patch("search_service.scrape_url_content", return_value=""), patch(
            "search_service.index_meilisearch_results",
            return_value=True,
        ):
            context, _ = execute_web_search(
                "latest gemma",
                {
                    "search_provider": "legacy",
                    "searxng_enabled": True,
                    "meilisearch_enabled": True,
                },
            )

        self.assertFalse(mocked_searxng.called)
        self.assertTrue(mocked_legacy.called)
        self.assertIn("Legacy", context)


if __name__ == "__main__":
    unittest.main()
