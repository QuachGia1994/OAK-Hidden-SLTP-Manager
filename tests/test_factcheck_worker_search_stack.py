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

    def test_ai_engine_is_optional_without_key(self):
        with patch.dict(factcheck_worker.os.environ, {}, clear=True):
            result = factcheck_worker.assess_with_ai(["claim"], [{"url": "https://reuters.com/a"}])
        self.assertIsNone(result)

    def test_ai_status_reports_missing_key(self):
        with patch.dict(factcheck_worker.os.environ, {}, clear=True), \
             patch.object(factcheck_worker, "_github_cli_token", return_value=""):
            result, status = factcheck_worker.assess_with_ai_detailed(["claim"], [{"url": "https://reuters.com/a"}])
        self.assertIsNone(result)
        self.assertEqual(status["state"], "missing_api_key")
        self.assertFalse(status["enabled"])
        self.assertEqual(status["provider"], "github")

    def test_ai_config_prefers_github_cli_token(self):
        with patch.dict(factcheck_worker.os.environ, {}, clear=True), \
             patch.object(factcheck_worker, "_github_cli_token", return_value="gho_test"):
            config = factcheck_worker._ai_config()
        self.assertEqual(config["provider"], "github")
        self.assertEqual(config["api_key"], "gho_test")
        self.assertEqual(config["model"], "openai/gpt-4.1-mini")

    def test_github_model_name_is_normalized_from_legacy_value(self):
        self.assertEqual(
            factcheck_worker._normalize_ai_model("github", "gpt-5-mini"),
            "openai/gpt-4.1-mini",
        )

    def test_openai_ai_request_uses_strict_evidence_schema(self):
        payload = factcheck_worker._build_ai_request("openai", "gpt-5-mini", {"claims": ["claim"], "evidence": []})
        self.assertEqual(payload["model"], "gpt-5-mini")
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertIn("Do not add facts or URLs", payload["input"][0]["content"])

    def test_github_ai_request_uses_chat_completions_schema(self):
        payload = factcheck_worker._build_ai_request("github", "openai/gpt-4.1-mini", {"claims": ["claim"], "evidence": []})
        self.assertEqual(payload["model"], "openai/gpt-4.1-mini")
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertIn("Do not add facts or URLs", payload["messages"][0]["content"])

    def test_google_search_falls_back_to_news_without_cse_credentials(self):
        news_hit = {"title": "News", "url": "https://news.google.com/a", "engine": "google"}
        with patch.dict(factcheck_worker.os.environ, {}, clear=True), \
             patch.object(factcheck_worker, "search_google_news", return_value=[news_hit]) as news_mock:
            self.assertEqual(factcheck_worker.search_google_web("claim"), [news_hit])
        news_mock.assert_called_once_with("claim")

    def test_high_overlap_evidence_counts_as_support(self):
        claim = "World Health Organization was founded in 1948"
        evidence = "World Health Organization founded in 1948 - official history"
        self.assertTrue(factcheck_worker.check_agreement(claim, evidence))

    def test_generic_khong_does_not_count_as_refutation(self):
        claim = "Iran nuclear site was damaged"
        evidence = "Nha may dien hat nhan khong bi hu hong nghiem trong trong dot tan cong"
        self.assertIsNone(factcheck_worker.check_agreement(claim, evidence))

    def test_unsafe_source_url_is_rejected(self):
        source = {"url": "javascript:alert(1)", "engine": "duckduckgo", "match_hits": 5, "relevance": 1}
        self.assertFalse(factcheck_worker.should_keep_source(source))


if __name__ == "__main__":
    unittest.main()
