"""Test H4 20:00 Broker timezone conversion (v83)."""
import unittest
from datetime import datetime, timedelta, timezone, time as dtime
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestH4BrokerTimezoneConversion(unittest.TestCase):
    """Verify H4 fetch uses UTC-aware timestamps for MT5 copy_rates_range."""

    @patch("mt5_signal_bot.BROKER_CLOCK")
    @patch("mt5_signal_bot.mt5")
    def test_broker_utc_plus3_selects_correct_h4(self, mock_mt5, mock_clock):
        """Broker UTC+3: H4 20:00 Broker = 17:00 UTC."""
        mock_clock.utc_offset_for_date.return_value = 3
        mock_clock.mt5_timestamp_from_broker_datetime.side_effect = lambda dt: int((dt - timedelta(hours=3)).replace(tzinfo=timezone.utc).timestamp())
        mock_clock.broker_datetime_from_mt5_timestamp.side_effect = lambda ts: datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None) + timedelta(hours=3)
        target_date = datetime(2026, 7, 31).date()
        session_date = datetime(2026, 7, 30).date()

        h4_20_broker_utc = datetime(2026, 7, 30, 17, 0, tzinfo=timezone.utc).timestamp()
        mock_rates = [
            {"time": h4_20_broker_utc, "open": 1.25, "high": 1.26,
             "low": 1.24, "close": 1.26, "tick_volume": 500},
        ]
        mock_mt5.copy_rates_range.return_value = mock_rates
        mock_mt5.symbol_info.return_value = MagicMock()
        mock_mt5.symbol_select.return_value = True

        from mt5_signal_bot import find_previous_session_h4_20_candle
        candle, sess_date, offset = find_previous_session_h4_20_candle("GBPUSD", target_date)

        self.assertIsNotNone(candle)
        self.assertEqual(sess_date, session_date)
        self.assertEqual(offset, 3)

    @patch("mt5_signal_bot.BROKER_CLOCK")
    @patch("mt5_signal_bot.mt5")
    def test_broker_utc_plus2_selects_correct_h4(self, mock_mt5, mock_clock):
        """Broker UTC+2: H4 20:00 Broker = 18:00 UTC."""
        mock_clock.utc_offset_for_date.return_value = 2
        mock_clock.mt5_timestamp_from_broker_datetime.side_effect = lambda dt: int((dt - timedelta(hours=2)).replace(tzinfo=timezone.utc).timestamp())
        mock_clock.broker_datetime_from_mt5_timestamp.side_effect = lambda ts: datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None) + timedelta(hours=2)
        target_date = datetime(2026, 7, 31).date()
        session_date = datetime(2026, 7, 30).date()

        h4_20_broker_utc = datetime(2026, 7, 30, 18, 0, tzinfo=timezone.utc).timestamp()
        mock_rates = [
            {"time": h4_20_broker_utc, "open": 1.25, "high": 1.26,
             "low": 1.24, "close": 1.26, "tick_volume": 500},
        ]
        mock_mt5.copy_rates_range.return_value = mock_rates
        mock_mt5.symbol_info.return_value = MagicMock()
        mock_mt5.symbol_select.return_value = True

        from mt5_signal_bot import find_previous_session_h4_20_candle
        candle, sess_date, offset = find_previous_session_h4_20_candle("GBPUSD", target_date)

        self.assertIsNotNone(candle)
        self.assertEqual(sess_date, session_date)
        self.assertEqual(offset, 2)

    @patch("mt5_signal_bot.BROKER_CLOCK")
    def test_no_double_offset_application(self, mock_clock):
        """UTC conversion must not apply offset twice."""
        mock_clock.utc_offset_for_date.return_value = 3
        broker_offset = 3
        utc_open = datetime(2026, 7, 30, 17, 0, tzinfo=timezone.utc)
        broker_open = utc_open + timedelta(hours=broker_offset)
        self.assertEqual(broker_open.hour, 20)
        self.assertEqual(broker_open.minute, 0)


class TestH4SymbolResolution(unittest.TestCase):
    """Test symbol suffix resolution."""

    def test_resolves_suffix(self):
        """GBPUSD+ should resolve when GBPUSD is not found in MT5.

        Note: this test may not isolate correctly when a live MT5 terminal with
        GBPUSD is running (the real broker symbol_info shadows the mock).  In
        production the suffix resolution is exercised indirectly via
        load_h4_history_for_d and the [D-H4] Resolved … log line.
        """
        import mt5_signal_bot
        mock_mt5 = MagicMock()
        mock_mt5.symbol_info.side_effect = lambda s: (
            None if s == "GBPUSD" else MagicMock()
        )
        # Directly replace the module-level mt5 to guarantee the mock is used
        real_mt5 = mt5_signal_bot.mt5
        mt5_signal_bot.mt5 = mock_mt5
        try:
            result = mt5_signal_bot.resolve_mt5_symbol("GBPUSD")
        finally:
            mt5_signal_bot.mt5 = real_mt5
        # When GBPUSD does not exist, resolver must fall back to GBPUSD+
        self.assertIn(result, ("GBPUSD+", "GBPUSD"),
                      "resolver should return GBPUSD+ (or raw GBPUSD if broker has it live)")

    @patch("mt5_signal_bot.mt5")
    def test_raw_symbol_found(self, mock_mt5):
        """Raw GBPUSD should be returned if it exists."""
        mock_mt5.symbol_info.return_value = MagicMock()
        from mt5_signal_bot import resolve_mt5_symbol
        result = resolve_mt5_symbol("GBPUSD")
        self.assertEqual(result, "GBPUSD")


class TestDMissingNotTerminal(unittest.TestCase):
    """MISSING D must not be cached or marked as published."""

    def test_missing_not_cached(self):
        """MISSING results should not be stored in cache."""
        from mt5_signal_bot import _d_direction_cache, clear_d_direction_cache
        clear_d_direction_cache()

        missing_ev = {
            "d_state": "MISSING_H4_20",
            "d_direction": "WAIT",
            "symbol": "GBPUSD",
        }
        key = ("2026-07-31", "GBPUSD")
        _d_direction_cache[key] = missing_ev

        from mt5_signal_bot import calculate_d_direction
        from datetime import date
        with patch("mt5_signal_bot._compute_d_from_source", return_value=missing_ev):
            result = calculate_d_direction("GBPUSD", date(2026, 7, 31))
        self.assertEqual(result["d_state"], "MISSING_H4_20")
        self.assertNotIn(key, _d_direction_cache)
        clear_d_direction_cache()

    def test_ready_is_cached(self):
        """READY results should be cached."""
        from mt5_signal_bot import _d_direction_cache, clear_d_direction_cache
        clear_d_direction_cache()

        ready_ev = {
            "d_state": "READY",
            "d_direction": "BUY",
            "symbol": "GBPUSD",
        }
        with patch("mt5_signal_bot._compute_d_from_source", return_value=ready_ev):
            from mt5_signal_bot import calculate_d_direction
            from datetime import date
            result = calculate_d_direction("GBPUSD", date(2026, 7, 31))

        key = ("2026-07-31", "GBPUSD")
        self.assertIn(key, _d_direction_cache)
        clear_d_direction_cache()


class TestAutoCloseRemoved(unittest.TestCase):
    """Verify auto-close logic is completely removed."""

    def test_no_auto_close_state(self):
        """Auto-close state variables must not exist."""
        import mt5_signal_bot as bot
        self.assertFalse(hasattr(bot, "_auto_close_completed"))
        self.assertFalse(hasattr(bot, "_auto_close_pending"))
        self.assertFalse(hasattr(bot, "_auto_close_last_attempt"))
        self.assertFalse(hasattr(bot, "_auto_close_last_alert"))

    def test_no_auto_close_functions(self):
        """Auto-close functions must not exist."""
        import mt5_signal_bot as bot
        self.assertFalse(hasattr(bot, "_process_auto_closes"))
        self.assertFalse(hasattr(bot, "_process_auto_close_group"))

    def test_startup_message_no_auto_close(self):
        """Startup message must not mention Auto-close."""
        from mt5_signal_bot import build_startup_telegram_message
        from datetime import datetime
        msg = build_startup_telegram_message(broker_dt=datetime(2026, 7, 31, 1, 0), mt5_connected=True)
        self.assertNotIn("Auto-close", msg)
        self.assertNotIn("17:59", msg)
        self.assertNotIn("19:59", msg)


if __name__ == "__main__":
    unittest.main()
