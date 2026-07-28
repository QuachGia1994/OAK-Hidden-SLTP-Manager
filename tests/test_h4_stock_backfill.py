"""Tests for deep H=4 history rebuilding."""
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

    def test_rebuilds_only_h4_for_requested_weekday_sessions(self) -> None:
        now = datetime(2026, 7, 17, 12, 0)
        with patch.object(mt5_signal_bot, "mt5_ready", True), patch.object(
            mt5_signal_bot, "get_broker_time", return_value=now
        ), patch.object(mt5_signal_bot, "rebuild_slot_signal", return_value=True) as rebuild:
            count = mt5_signal_bot.rebuild_h4_history(session_count=5)

        self.assertEqual(count, 5)
        self.assertEqual([call.args[1] for call in rebuild.call_args_list], [4, 4, 4, 4, 4])
        rebuilt_dates = [call.args[0].date().isoformat() for call in rebuild.call_args_list]
        self.assertEqual(rebuilt_dates, ["2026-07-13", "2026-07-14", "2026-07-15", "2026-07-16", "2026-07-17"])

    def test_before_h4_cutoff_excludes_the_current_date(self) -> None:
        now = datetime(2026, 7, 17, 3, 59)
        with patch.object(mt5_signal_bot, "mt5_ready", True), patch.object(
            mt5_signal_bot, "get_broker_time", return_value=now
        ), patch.object(mt5_signal_bot, "rebuild_slot_signal", return_value=True) as rebuild:
            mt5_signal_bot.rebuild_h4_history(session_count=1)

        self.assertEqual(rebuild.call_args.args[0].date().isoformat(), "2026-07-16")

    def test_h4_cutoff_includes_the_current_date(self) -> None:
        now = datetime(2026, 7, 17, 4, 0)
        with patch.object(mt5_signal_bot, "mt5_ready", True), patch.object(
            mt5_signal_bot, "get_broker_time", return_value=now
        ), patch.object(mt5_signal_bot, "rebuild_slot_signal", return_value=True) as rebuild:
            mt5_signal_bot.rebuild_h4_history(session_count=1)

        self.assertEqual(rebuild.call_args.args[0].date().isoformat(), "2026-07-17")


if __name__ == "__main__":
    unittest.main()
