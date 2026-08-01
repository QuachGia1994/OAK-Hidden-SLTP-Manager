import unittest
from datetime import date

from domain.stock_scanner import Direction, scan_d1_linear, scan_symbol_d1


class StockFilterD1Tests(unittest.TestCase):
    def test_future_bar_is_not_used(self):
        bars = [
            {"date": "2026-07-30", "close": 10, "open": 9, "high": 10, "low": 9, "volume": 1},
            {"date": "2026-07-31", "close": 11, "open": 10, "high": 11, "low": 10, "volume": 2},
            {"date": "2026-08-02", "close": 1, "open": 1, "high": 1, "low": 1, "volume": 999},
        ]
        result = scan_symbol_d1("AAA", bars, date(2026, 8, 1))
        self.assertEqual(result.direction, Direction.BUY)
        self.assertEqual(result.latest_close, 11)

    def test_results_are_ranked_deterministically_and_advisory_only(self):
        payload = scan_d1_linear({
            "BBB": [{"date": "2026-07-30", "open": 9, "high": 10, "low": 9, "close": 10}, {"date": "2026-07-31", "open": 10, "high": 12, "low": 10, "close": 12}],
            "AAA": [{"date": "2026-07-30", "open": 9, "high": 10, "low": 9, "close": 10}, {"date": "2026-07-31", "open": 10, "high": 11, "low": 10, "close": 11}],
        }, date(2026, 8, 1), capital=100)
        self.assertTrue(payload["advisory_only"])
        self.assertFalse(payload["orders_submitted"])
        self.assertEqual(payload["recommendations"][0]["symbol"], "BBB")


if __name__ == "__main__":
    unittest.main()
