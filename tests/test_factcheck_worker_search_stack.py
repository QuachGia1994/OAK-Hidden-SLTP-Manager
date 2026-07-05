import unittest
from unittest.mock import patch

import factcheck_worker


class FactcheckWorkerSearchStackTests(unittest.TestCase):
    def test_search_web_uses_google_then_duckduckgo(self):
        google_hit = {"title": "Google hit", "url": "https://example.com/google", "snippet": "", "engine": "google"}
        ddg_hit = {"title": "DDG hit", "url": "https://example.com/ddg", "snippet": "", "engine": "duckduckgo"}

        with patch.object(factcheck_worker, "search_google_web", return_value=[google_hit]) as google_mock, \
             patch.object(factcheck_worker, "search_duckduckgo", return_value=[ddg_hit]) as ddg_mock:
            results = factcheck_worker.search_web("gold price today")

        self.assertEqual(results, [google_hit, ddg_hit])
        google_mock.assert_called_once_with("gold price today")
        ddg_mock.assert_called_once_with("gold price today")


if __name__ == "__main__":
    unittest.main()
