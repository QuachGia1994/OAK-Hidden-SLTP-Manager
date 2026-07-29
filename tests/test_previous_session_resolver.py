"""Tests for resolve_previous_broker_session and Monday WAIT persistence."""
from __future__ import annotations

from datetime import date, datetime
import unittest
from unittest.mock import MagicMock, patch

import sys
_mock_mt5 = MagicMock()
sys.modules.setdefault("MetaTrader5", _mock_mt5)

from mt5_signal_bot import (
    ACTIVE_HOURS,
    SIGNAL_LOGIC_VERSION,
    _previous_session_cache,
    get_pair_direction,
    is_deactivated_signal_slot,
    resolve_previous_broker_session,
)


class PreviousSessionResolverTests(unittest.TestCase):
    """Verify that resolve_previous_broker_session skips weekends and holidays."""

    def setUp(self):
        _previous_session_cache.clear()
        self.timestamp_patch = patch(
            "mt5_signal_bot.broker_time_to_ts",
            side_effect=lambda broker_dt, _hour: broker_dt.date(),
        )
        self.timestamp_patch.start()

    def tearDown(self):
        self.timestamp_patch.stop()

    @patch("mt5_signal_bot.get_candle_by_ts", return_value={"time": 1})
    def test_monday_resolves_to_friday(self, _read_candle):
        broker_dt = datetime(2026, 7, 27, 9, 0)  # Monday
        result = resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15)
        self.assertEqual(result, date(2026, 7, 24))  # Friday

    @patch("mt5_signal_bot.get_candle_by_ts", return_value={"time": 1})
    def test_tuesday_resolves_to_monday(self, _read_candle):
        broker_dt = datetime(2026, 7, 28, 9, 0)  # Tuesday
        result = resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15)
        self.assertEqual(result, date(2026, 7, 27))  # Monday

    @patch("mt5_signal_bot.get_candle_by_ts", return_value=None)
    def test_returns_none_when_no_session_found(self, _read_candle):
        broker_dt = datetime(2026, 7, 27, 9, 0)
        result = resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15)
        self.assertIsNone(result)

    @patch("mt5_signal_bot.get_candle_by_ts")
    def test_skips_holiday_and_finds_earlier_session(self, read_candle):
        read_candle.side_effect = (None, {"time": 1})
        broker_dt = datetime(2026, 7, 24, 9, 0)  # Friday
        result = resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15)
        self.assertEqual(result, date(2026, 7, 22))

    @patch("mt5_signal_bot.get_candle_by_ts", return_value={"time": 1})
    def test_caches_result(self, read_candle):
        broker_dt = datetime(2026, 7, 27, 9, 0)
        result1 = resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15)
        result2 = resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15)
        self.assertEqual(result1, result2)
        read_candle.assert_called_once()

    @patch("mt5_signal_bot.get_candle_by_ts")
    def test_failed_lookup_is_not_cached(self, read_candle):
        broker_dt = datetime(2026, 7, 27, 9, 0)
        read_candle.return_value = None
        self.assertIsNone(
            resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15)
        )
        read_candle.return_value = {"time": 1}
        self.assertEqual(
            resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15),
            date(2026, 7, 24),
        )

    @patch("mt5_signal_bot.get_candle_by_ts", return_value={"time": 1})
    def test_wednesday_resolves_to_tuesday(self, _read_candle):
        broker_dt = datetime(2026, 7, 22, 9, 0)  # Wednesday
        result = resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15)
        self.assertEqual(result, date(2026, 7, 21))  # Tuesday

    @patch("mt5_signal_bot.get_candle_by_ts", return_value={"time": 1})
    def test_friday_resolves_to_thursday(self, _read_candle):
        broker_dt = datetime(2026, 7, 24, 9, 0)  # Friday
        result = resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15)
        self.assertEqual(result, date(2026, 7, 23))  # Thursday


class WaitRecordContractTests(unittest.TestCase):
    """Verify WAIT records have proper pair_dirs for dashboard display."""

    def test_wait_pair_dirs_includes_xauusd_and_gbp_pairs(self):
        """When signal is WAIT, pair_dirs must contain XAUUSD, GBPUSD, GBPAUD."""
        for h in (3, 7, 9, 12, 14, 16):
            result = get_pair_direction(h, "WAIT", None, full_result=None)
            self.assertEqual(result.get("XAUUSD"), "WAIT")
            self.assertEqual(result.get("GBPUSD"), "WAIT")
            self.assertEqual(result.get("GBPAUD"), "WAIT")

    def test_signal_logic_version_is_71(self):
        self.assertEqual(SIGNAL_LOGIC_VERSION, 71)

    def test_no_slot_is_deactivated_v65(self):
        """Since v65, no active slot is deactivated on any weekday."""
        thursday = datetime(2026, 7, 30, 3, 0)
        self.assertFalse(is_deactivated_signal_slot(thursday, 3))
        self.assertNotIn(4, ACTIVE_HOURS)
        tuesday = datetime(2026, 7, 28, 3, 0)
        self.assertFalse(is_deactivated_signal_slot(tuesday, 3))


if __name__ == "__main__":
    unittest.main()
