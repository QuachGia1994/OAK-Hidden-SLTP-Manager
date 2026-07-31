"""Test timeframe cache isolation for candle objects (v84)."""
import unittest
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import mt5_signal_bot


class TestTimeframeCacheIsolation(unittest.TestCase):
    """Verify M30 and H4 candles at the same symbol/timestamp do not overwrite or cross-read."""

    def setUp(self):
        mt5_signal_bot.clear_history_cache()

    def test_m30_and_h4_cache_keys_are_isolated(self):
        target_ts = 1750000000

        m30_candle = {"open": 100.0, "close": 105.0, "time": target_ts, "tf": "M30"}
        h4_candle = {"open": 100.0, "close": 115.0, "time": target_ts, "tf": "H4"}

        mt5_signal_bot._cache[("GBPUSD+", 30, target_ts)] = m30_candle
        mt5_signal_bot._cache[("GBPUSD+", 16388, target_ts)] = h4_candle

        res_m30 = mt5_signal_bot._cache.get(("GBPUSD+", 30, target_ts))
        res_h4 = mt5_signal_bot._cache.get(("GBPUSD+", 16388, target_ts))

        self.assertEqual(res_m30["tf"], "M30")
        self.assertEqual(res_h4["tf"], "H4")

    @patch("mt5_signal_bot.mt5")
    def test_requesting_h4_does_not_return_cached_m30(self, mock_mt5):
        mock_mt5.symbol_select.return_value = True
        target_ts = 1750000000

        m30_candle = {"open": 1.2500, "high": 1.2520, "low": 1.2490, "close": 1.2510, "time": target_ts}
        h4_raw = [{"open": 1.2500, "high": 1.2600, "low": 1.2450, "close": 1.2580, "time": target_ts}]
        mock_mt5.copy_rates_range.return_value = h4_raw

        # Put M30 in cache
        mt5_signal_bot._cache[("GBPUSD+", 30, target_ts)] = m30_candle

        # Request H4 at same timestamp (16388 is TIMEFRAME_H4)
        result = mt5_signal_bot.get_candle_by_ts("GBPUSD+", 16388, target_ts)
        self.assertIsNotNone(result)
        self.assertEqual(result["close"], 1.2580)


if __name__ == "__main__":
    unittest.main()
