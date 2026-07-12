import unittest
from datetime import datetime, timezone

from mt5_signal_bot import _parse_news_for_dashboard, get_pair_direction, select_signals_for_dashboard


class DashboardSignalSelectionTests(unittest.TestCase):
    def test_keeps_all_signal_days_when_pair_dirs_exist(self):
        signals = [
            {"date": "2026-07-03", "hour": 2, "pair_dirs": {"XAUUSD": "BUY"}},
            {"date": "2026-07-03", "hour": 3, "pair_dirs": {"XAUUSD": "SELL"}},
            {"date": "2026-07-04", "hour": 2, "pair_dirs": {"XAUUSD": "BUY"}},
            {"date": "2026-07-04", "hour": 3, "pair_dirs": {}},
        ]

        result = select_signals_for_dashboard(signals)

        self.assertEqual(
            result,
            [
                {"date": "2026-07-03", "hour": 2, "pair_dirs": {"XAUUSD": "BUY"}},
                {"date": "2026-07-03", "hour": 3, "pair_dirs": {"XAUUSD": "SELL"}},
                {"date": "2026-07-04", "hour": 2, "pair_dirs": {"XAUUSD": "BUY"}},
            ],
        )

    def test_h6_xauusd_only_no_gbp_pair_dirs(self):
        """H=5-8: Focus GA only — pair_dirs has XAU only (no GBP map)."""
        for broker_dt in (
            datetime(2026, 7, 7, tzinfo=timezone.utc),
            datetime(2026, 7, 9, tzinfo=timezone.utc),
        ):
            with self.subTest(weekday=broker_dt.weekday()):
                    self.assertEqual(
                        get_pair_direction(6, "BUY", broker_dt),
                        {"XAUUSD": "BUY"},
                    )

    def test_news_parse_marks_vietnam_timezone(self):
        item = _parse_news_for_dashboard(["19:30 CAD [HIGH] Employment Change"])[0]
        self.assertEqual(item["local_time"], "19:30")
        self.assertEqual(item["time_zone"], "Asia/Bangkok")


if __name__ == "__main__":
    unittest.main()
