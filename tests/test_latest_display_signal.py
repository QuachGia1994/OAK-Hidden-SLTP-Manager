import unittest

from utils import get_latest_display_signal


class LatestDisplaySignalTests(unittest.TestCase):
    def test_prefers_today_highest_hour(self):
        signals = [
            {"date": "2026-07-08", "hour": 15, "pair_dirs": {"XAUUSD": "SELL"}},
            {"date": "2026-07-09", "hour": 6, "pair_dirs": {"XAUUSD": "BUY"}},
            {"date": "2026-07-09", "hour": 8, "pair_dirs": {"XAUUSD": "SELL", "GBPAUD": "BUY"}},
            {"date": "2026-07-03", "hour": 16, "pair_dirs": {"XAUUSD": "BUY"}},
        ]

        latest = get_latest_display_signal(signals, today="2026-07-09")

        self.assertEqual(latest["hour"], 8)
        self.assertEqual(latest["pair_dirs"]["GBPAUD"], "BUY")

    def test_falls_back_to_latest_dated_row_when_no_today(self):
        signals = [
            {"date": "2026-07-03", "hour": 2, "pair_dirs": {"XAUUSD": "BUY"}},
            {"date": "2026-07-07", "hour": 14, "pair_dirs": {"XAUUSD": "SELL"}},
        ]

        latest = get_latest_display_signal(signals, today="2026-07-09")

        self.assertEqual(latest["date"], "2026-07-07")
        self.assertEqual(latest["hour"], 14)

    def test_can_disable_old_signal_fallback(self):
        signals = [
            {"date": "2026-07-10", "hour": 15, "pair_dirs": {"XAUUSD": "BUY"}},
        ]

        latest = get_latest_display_signal(
            signals,
            today="2026-07-11",
            allow_fallback=False,
        )

        self.assertIsNone(latest)


if __name__ == "__main__":
    unittest.main()
