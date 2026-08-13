# -*- coding: utf-8 -*-
"""Period-scoped public performance contract tests."""
from datetime import datetime, timezone
import unittest

from services.audit_dashboard_publisher import (
    PUBLIC_PERIOD_DAYS,
    period_since_utc,
    public_account_id,
)


class TestPeriodSemantics(unittest.TestCase):
    def test_period_days_map(self):
        self.assertIsNone(PUBLIC_PERIOD_DAYS["all"])
        self.assertEqual(PUBLIC_PERIOD_DAYS["1w"], 7)
        self.assertEqual(PUBLIC_PERIOD_DAYS["1m"], 30)
        self.assertEqual(PUBLIC_PERIOD_DAYS["3m"], 90)
        self.assertEqual(PUBLIC_PERIOD_DAYS["6m"], 180)
        self.assertEqual(PUBLIC_PERIOD_DAYS["1y"], 365)

    def test_period_since_utc_all(self):
        self.assertIsNone(period_since_utc("all"))

    def test_period_since_utc_1m_boundary(self):
        now = datetime(2026, 8, 14, 0, 0, 0, tzinfo=timezone.utc)
        since = period_since_utc("1m", now=now)
        self.assertEqual(since.isoformat(), "2026-07-15T00:00:00+00:00")

    def test_public_account_id_stable_and_non_raw(self):
        a = public_account_id("Vantage", secret="s")
        b = public_account_id("Vantage", secret="s")
        c = public_account_id("ICMarkets", secret="s")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertNotEqual(a, "Vantage")
        self.assertEqual(len(a), 16)


if __name__ == "__main__":
    unittest.main()
