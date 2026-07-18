"""Tests for publishing advisory-only results to the web dashboard."""
import json
import unittest

from services.stock_dashboard_publisher import (
    DashboardPublisherConfig,
    publish_stock_advisory,
)


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self) -> bytes:
        return b'{"ok":true}'


class StockDashboardPublisherTests(unittest.TestCase):
    def test_publisher_uses_authenticated_advisor_endpoint(self) -> None:
        captured = {}

        def opener(request, timeout):
            captured["request"] = request
            captured["timeout"] = timeout
            return _Response()

        result = publish_stock_advisory(
            {"advisory_only": True, "orders_submitted": False},
            DashboardPublisherConfig("https://oak.example", "api-key"),
            opener=opener,
        )

        request = captured["request"]
        self.assertTrue(result.pushed)
        self.assertEqual(request.full_url, "https://oak.example/api/stock-advisor")
        self.assertEqual(request.headers["X-api-key"], "api-key")
        self.assertFalse(json.loads(request.data)["orders_submitted"])

    def test_missing_dashboard_url_is_a_safe_local_only_result(self) -> None:
        result = publish_stock_advisory(
            {"advisory_only": True},
            DashboardPublisherConfig("", ""),
        )

        self.assertFalse(result.pushed)
        self.assertEqual(result.status, "not_configured")


if __name__ == "__main__":
    unittest.main()
