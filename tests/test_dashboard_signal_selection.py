import unittest

from mt5_signal_bot import select_signals_for_dashboard


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


if __name__ == "__main__":
    unittest.main()
