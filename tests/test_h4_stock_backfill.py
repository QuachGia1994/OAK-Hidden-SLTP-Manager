"""Tests for deep H=4 history rebuilding (retired — H4 is no longer a signal slot)."""
from datetime import datetime, timezone
import inspect
import unittest
from unittest.mock import patch

import mt5_signal_bot


class H4BackfillTests(unittest.TestCase):
    def test_signal_log_write_is_atomic(self) -> None:
        self.assertIn("os.replace", inspect.getsource(mt5_signal_bot._write_signals_log_atomic))

    def test_exact_range_supports_history_deeper_than_5000_bars(self) -> None:
        target = datetime(2025, 7, 17, 4, 35, tzinfo=timezone.utc)
        timestamp = int(target.timestamp())
        candle = {"time": timestamp, "open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0}
        with patch.object(mt5_signal_bot.mt5, "symbol_select", return_value=True), patch.object(
            mt5_signal_bot.mt5, "copy_rates_range", return_value=[candle]
        ), patch.object(mt5_signal_bot.mt5, "copy_rates_from_pos") as recent:
            result = mt5_signal_bot.get_candle_by_ts("GBPUSD", mt5_signal_bot.mt5.TIMEFRAME_M5, timestamp)

        self.assertEqual(result, candle)
        recent.assert_not_called()

    def test_rebuild_h4_history_is_removed(self) -> None:
        self.assertFalse(hasattr(mt5_signal_bot, "rebuild_h4_history"))


if __name__ == "__main__":
    unittest.main()
