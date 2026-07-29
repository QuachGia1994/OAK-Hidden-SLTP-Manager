"""Tests for resolve_previous_broker_session and Monday WAIT persistence."""
from __future__ import annotations

from datetime import date, datetime, timedelta
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


def _mock_candle_present(*args, **kwargs):
    """Mock copy_rates_from that returns a bar for any weekday."""
    return [1]


def _mock_candle_absent(*args, **kwargs):
    """Mock copy_rates_from that returns no bars."""
    return None


class PreviousSessionResolverTests(unittest.TestCase):
    """Verify that resolve_previous_broker_session skips weekends and holidays."""

    def setUp(self):
        _previous_session_cache.clear()

    @patch("mt5_signal_bot.mt5.copy_rates_from", _mock_candle_present)
    def test_monday_resolves_to_friday(self):
        broker_dt = datetime(2026, 7, 27, 9, 0)  # Monday
        result = resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15)
        self.assertEqual(result, date(2026, 7, 24))  # Friday

    @patch("mt5_signal_bot.mt5.copy_rates_from", _mock_candle_present)
    def test_tuesday_resolves_to_monday(self):
        broker_dt = datetime(2026, 7, 28, 9, 0)  # Tuesday
        result = resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15)
        self.assertEqual(result, date(2026, 7, 27))  # Monday

    @patch("mt5_signal_bot.mt5.copy_rates_from", _mock_candle_absent)
    def test_returns_none_when_no_session_found(self):
        broker_dt = datetime(2026, 7, 27, 9, 0)
        result = resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15)
        self.assertIsNone(result)

    @patch("mt5_signal_bot.mt5.copy_rates_from")
    def test_skips_holiday_and_finds_earlier_session(self, mock_copy):
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                return None  # Thursday has no data
            return [1]  # Wednesday has data
        mock_copy.side_effect = side_effect
        broker_dt = datetime(2026, 7, 24, 9, 0)  # Friday
        result = resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15)
        self.assertIsNotNone(result)

    @patch("mt5_signal_bot.mt5.copy_rates_from", _mock_candle_present)
    def test_caches_result(self):
        broker_dt = datetime(2026, 7, 27, 9, 0)
        result1 = resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15)
        result2 = resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15)
        self.assertEqual(result1, result2)

    @patch("mt5_signal_bot.mt5.copy_rates_from", _mock_candle_present)
    def test_wednesday_resolves_to_tuesday(self):
        broker_dt = datetime(2026, 7, 22, 9, 0)  # Wednesday
        result = resolve_previous_broker_session(broker_dt, "GBPAUD", _mock_mt5.TIMEFRAME_M15)
        self.assertEqual(result, date(2026, 7, 21))  # Tuesday

    @patch("mt5_signal_bot.mt5.copy_rates_from", _mock_candle_present)
    def test_friday_resolves_to_thursday(self):
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

    def test_signal_logic_version_is_70(self):
        self.assertEqual(SIGNAL_LOGIC_VERSION, 70)

    def test_no_slot_is_deactivated_v65(self):
        """Since v65, no active slot is deactivated on any weekday."""
        thursday = datetime(2026, 7, 30, 3, 0)
        self.assertFalse(is_deactivated_signal_slot(thursday, 3))
        self.assertNotIn(4, ACTIVE_HOURS)
        tuesday = datetime(2026, 7, 28, 3, 0)
        self.assertFalse(is_deactivated_signal_slot(tuesday, 3))


if __name__ == "__main__":
    unittest.main()
