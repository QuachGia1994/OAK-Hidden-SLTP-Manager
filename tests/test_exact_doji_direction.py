"""Exact DOJI detection: open == close exactly → DOJI; 1-point difference → TANG/GIAM."""

import unittest
from mt5_signal_bot import exact_candle_direction, _m30_candle_direction


class ExactDojiDirectionTests(unittest.TestCase):
    def test_exact_equal_is_doji(self):
        candle = {"open": 1.23456, "close": 1.23456, "high": 1.23500, "low": 1.23400}
        self.assertEqual(exact_candle_direction(candle), "DOJI")

    def test_one_point_tang(self):
        candle = {"open": 1.23456, "close": 1.23457, "high": 1.23500, "low": 1.23400}
        self.assertEqual(exact_candle_direction(candle), "TANG")

    def test_one_point_giam(self):
        candle = {"open": 1.23456, "close": 1.23455, "high": 1.23500, "low": 1.23400}
        self.assertEqual(exact_candle_direction(candle), "GIAM")

    def test_very_small_body_not_doji(self):
        candle = {"open": 2345.12, "close": 2345.13, "high": 2346.00, "low": 2344.00}
        self.assertEqual(exact_candle_direction(candle), "TANG")

    def test_string_prices_exact_equal(self):
        candle = {"open": "1.23456", "close": "1.23456", "high": "1.23500", "low": "1.23400"}
        self.assertEqual(exact_candle_direction(candle), "DOJI")

    def test_none_candle(self):
        self.assertIsNone(exact_candle_direction(None))

    def test_missing_fields(self):
        self.assertIsNone(exact_candle_direction({"open": 1.0}))

    def test_m30_candle_direction_delegates_to_exact(self):
        candle = {"open": 1.23456, "close": 1.23456, "high": 1.23500, "low": 1.23400}
        self.assertEqual(_m30_candle_direction(candle), "DOJI")

    def test_m30_candle_direction_none(self):
        self.assertIsNone(_m30_candle_direction(None))


if __name__ == "__main__":
    unittest.main()
