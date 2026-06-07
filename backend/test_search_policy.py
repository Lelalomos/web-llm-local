import unittest

from search_policy import dedupe_search_results, normalize_search_query, rank_search_results, should_auto_search


class SearchPolicyTests(unittest.TestCase):
    def test_auto_search_detects_time_sensitive_queries(self):
        self.assertTrue(should_auto_search("latest gemma release news"))
        self.assertTrue(should_auto_search("AAPL stock price today"))
        self.assertTrue(should_auto_search("ข่าวหุ้นไทยล่าสุด"))

    def test_auto_search_skips_local_task_queries(self):
        self.assertFalse(should_auto_search("write code to sort a list"))
        self.assertFalse(should_auto_search('Use the file content above to answer this prompt: summarize this file'))

    def test_query_normalizer_strips_file_wrapper(self):
        query = 'Context from uploaded file "notes.txt": --- START OF FILE CONTENT --- abc --- END OF FILE CONTENT --- Use the file content above to answer this prompt: latest nvidia news'
        self.assertEqual(normalize_search_query(query), "latest nvidia news")

    def test_query_normalizer_maps_thai_stock_queries(self):
        self.assertEqual(normalize_search_query("หุ้นไทยล่าสุด"), "SET index Thailand stock news")

    def test_ranking_prefers_trusted_matching_sources(self):
        ranked = rank_search_results(
            [
                {"title": "General roundup", "href": "https://example.com/story", "body": "latest gemma notes"},
                {"title": "Latest Gemma release", "href": "https://www.reuters.com/technology/story", "body": "gemma release update"},
            ],
            "latest gemma release",
        )
        self.assertEqual(ranked[0]["href"], "https://www.reuters.com/technology/story")

    def test_ranking_prefers_more_recent_results(self):
        ranked = rank_search_results(
            [
                {"title": "Gemma update 2025-05-01", "href": "https://example.com/old", "body": "gemma release"},
                {"title": "Gemma update 2099-06-07", "href": "https://example.com/new", "body": "gemma release"},
            ],
            "latest gemma update",
        )

        self.assertEqual(ranked[0]["href"], "https://example.com/new")

    def test_dedupe_search_results_removes_duplicate_urls(self):
        deduped = dedupe_search_results(
            [
                {"title": "Latest Gemma release", "href": "https://www.reuters.com/tech/gemma?utm_source=test", "body": "story one"},
                {"title": "Latest Gemma release", "href": "https://reuters.com/tech/gemma", "body": "story two"},
                {"title": "Another story", "href": "https://apnews.com/article/gemma", "body": "story three"},
            ]
        )

        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["href"], "https://www.reuters.com/tech/gemma?utm_source=test")


if __name__ == "__main__":
    unittest.main()
