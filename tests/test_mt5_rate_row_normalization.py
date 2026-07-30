"""MT5 rate row normalization: numpy.void and dict compatibility for v76."""

import unittest
from unittest.mock import patch

import numpy as np

from mt5_signal_bot import (
    _mt5_rate_field,
    _serialize_candle_ohlc,
    normalize_mt5_rate_row,
)

_MT5_DTYPE = [
    ("time", "<i8"),
    ("open", "<f8"),
    ("high", "<f8"),
    ("low", "<f8"),
    ("close", "<f8"),
    ("tick_volume", "<u8"),
    ("spread", "<i4"),
    ("real_volume", "<u8"),
]


def _make_numpy_row(**kwargs):
    defaults = {
        "time": 1234567890,
        "open": 1.1,
        "high": 1.3,
        "low": 1.0,
        "close": 1.2,
        "tick_volume": 123,
        "spread": 10,
        "real_volume": 20,
    }
    defaults.update(kwargs)
    rates = np.array(
        [tuple(defaults[k] for k, _ in _MT5_DTYPE)],
        dtype=_MT5_DTYPE,
    )
    return rates[0]


class Mt5RateFieldTests(unittest.TestCase):
    def test_dict_access(self):
        row = {"open": 1.1, "close": 1.2, "tick_volume": 100}
        self.assertEqual(_mt5_rate_field(row, "open"), 1.1)
        self.assertEqual(_mt5_rate_field(row, "tick_volume"), 100)

    def test_numpy_void_access(self):
        row = _make_numpy_row()
        self.assertEqual(type(row).__name__, "void")
        self.assertAlmostEqual(_mt5_rate_field(row, "open"), 1.1)
        self.assertEqual(_mt5_rate_field(row, "tick_volume"), 123)

    def test_numpy_void_returns_native_python_types(self):
        row = _make_numpy_row()
        value = _mt5_rate_field(row, "open")
        self.assertIsInstance(value, float)
        self.assertNotIsInstance(value, np.floating)
        tv = _mt5_rate_field(row, "tick_volume")
        self.assertIsInstance(tv, int)
        self.assertNotIsInstance(tv, np.integer)

    def test_dict_missing_field_with_default(self):
        row = {"open": 1.1}
        self.assertEqual(_mt5_rate_field(row, "tick_volume", 0), 0)

    def test_numpy_void_missing_field_with_default(self):
        row = _make_numpy_row()
        self.assertEqual(_mt5_rate_field(row, "nonexistent", 42), 42)

    def test_none_row_with_default(self):
        self.assertEqual(_mt5_rate_field(None, "open", 0), 0)

    def test_none_row_without_default_raises(self):
        with self.assertRaises(KeyError):
            _mt5_rate_field(None, "open")


class NormalizeMt5RateRowTests(unittest.TestCase):
    def test_numpy_void_normalizes_to_plain_dict(self):
        row = _make_numpy_row()
        result = normalize_mt5_rate_row(row)
        self.assertIsInstance(result, dict)
        self.assertAlmostEqual(result["open"], 1.1)
        self.assertAlmostEqual(result["high"], 1.3)
        self.assertAlmostEqual(result["low"], 1.0)
        self.assertAlmostEqual(result["close"], 1.2)
        self.assertEqual(result["tick_volume"], 123)
        self.assertEqual(result["spread"], 10)
        self.assertEqual(result["real_volume"], 20)
        self.assertEqual(result["time"], 1234567890)

    def test_all_values_are_native_python_types(self):
        row = _make_numpy_row()
        result = normalize_mt5_rate_row(row)
        for key in ("time", "tick_volume", "spread", "real_volume"):
            self.assertIsInstance(result[key], int, f"{key} should be int")
            self.assertNotIsInstance(result[key], np.integer, f"{key} should not be numpy int")
        for key in ("open", "high", "low", "close"):
            self.assertIsInstance(result[key], float, f"{key} should be float")
            self.assertNotIsInstance(result[key], np.floating, f"{key} should not be numpy float")

    def test_dict_passes_through(self):
        row = {
            "time": 1234567890,
            "open": 1.1,
            "high": 1.3,
            "low": 1.0,
            "close": 1.2,
        }
        result = normalize_mt5_rate_row(row)
        self.assertIsInstance(result, dict)
        self.assertEqual(result["tick_volume"], 0)
        self.assertEqual(result["spread"], 0)
        self.assertEqual(result["real_volume"], 0)

    def test_none_returns_none(self):
        self.assertIsNone(normalize_mt5_rate_row(None))

    def test_result_is_json_serializable(self):
        import json
        row = _make_numpy_row()
        result = normalize_mt5_rate_row(row)
        json.dumps(result)


class SerializeCandleOhlcTests(unittest.TestCase):
    def test_numpy_void_serializes_without_error(self):
        row = _make_numpy_row()
        serialized = _serialize_candle_ohlc(row, "GBPUSD")
        self.assertEqual(serialized["tick_volume"], 123)
        self.assertAlmostEqual(serialized["open"], 1.10000, places=5)

    def test_dict_with_tick_volume(self):
        candle = {
            "open": 2300.50,
            "high": 2305.00,
            "low": 2298.00,
            "close": 2303.00,
            "tick_volume": 456,
        }
        serialized = _serialize_candle_ohlc(candle, "XAUUSD")
        self.assertEqual(serialized["tick_volume"], 456)
        self.assertAlmostEqual(serialized["open"], 2300.50, places=2)

    def test_dict_missing_tick_volume_defaults_to_zero(self):
        candle = {
            "open": 1.1,
            "high": 1.3,
            "low": 1.0,
            "close": 1.2,
        }
        serialized = _serialize_candle_ohlc(candle, "GBPUSD")
        self.assertEqual(serialized["tick_volume"], 0)

    def test_none_returns_none(self):
        self.assertIsNone(_serialize_candle_ohlc(None, "GBPUSD"))

    def test_result_is_json_serializable(self):
        import json
        row = _make_numpy_row()
        serialized = _serialize_candle_ohlc(row, "GBPUSD")
        json.dumps(serialized)


class GetCandleByTsNormalizationTests(unittest.TestCase):
    """Verify get_candle_by_ts normalizes numpy rows at the boundary."""

    @patch("mt5_signal_bot.mt5")
    def test_returns_plain_dict_from_numpy_rates(self, mock_mt5):
        from mt5_signal_bot import get_candle_by_ts

        mock_mt5.symbol_select.return_value = True

        target_ts = 1234567890
        rates = np.array(
            [(target_ts, 1.1, 1.3, 1.0, 1.2, 123, 10, 20)],
            dtype=_MT5_DTYPE,
        )
        mock_mt5.copy_rates_range.return_value = rates

        result = get_candle_by_ts("GBPUSD", 16385, target_ts)
        self.assertIsNotNone(result)
        self.assertIsInstance(result, dict)
        self.assertAlmostEqual(result["open"], 1.1)
        self.assertEqual(result["tick_volume"], 123)
        self.assertIsInstance(result["tick_volume"], int)
        self.assertNotIsInstance(result["tick_volume"], np.integer)


if __name__ == "__main__":
    unittest.main()
