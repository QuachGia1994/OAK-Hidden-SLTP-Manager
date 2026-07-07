import unittest
from datetime import datetime, timezone

from mt5_signal_bot import get_pair_direction, select_signals_for_dashboard


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

    def test_h6_gbpaud_opposite(self):
        for broker_dt in (
            datetime(2026, 7, 7, tzinfo=timezone.utc),
            datetime(2026, 7, 9, tzinfo=timezone.utc),
        ):
            with self.subTest(weekday=broker_dt.weekday()):
                self.assertEqual(
                    get_pair_direction(6, "BUY", broker_dt),
                    {"XAUUSD": "BUY", "GBPAUD": "SELL", "GBPCAD": "--", "GBPUSD": "--", "GBPJPY": "--"},
                )


if __name__ == "__main__":
    unittest.main()
