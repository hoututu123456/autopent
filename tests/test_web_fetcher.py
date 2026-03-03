import unittest


class WebFetcherTests(unittest.TestCase):
    def test_fetch_blocks_private_hosts(self):
        from src.utils.web_searcher import WebSearcher

        with self.assertRaises(Exception):
            WebSearcher.fetch_url_text("http://127.0.0.1/", max_chars=1000)

        with self.assertRaises(Exception):
            WebSearcher.fetch_url_text("http://localhost/", max_chars=1000)

