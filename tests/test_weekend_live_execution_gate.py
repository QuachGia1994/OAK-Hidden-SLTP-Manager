"""v88 live weekend execution gate: off by default, on only with signal_live_weekends=true."""
import unittest
from datetime import datetime
from unittest.mock import patch

import mt5_signal_bot
from mt5_signal_bot import (
    TARGET_HOURS,
    _signal_live_weekends_enabled,
    get_live_target_hours,
    schedule_orders_for_signal,
)

SATURDAY = datetime(2026, 8, 1, 12)
SUNDAY = datetime(2026, 8, 2, 12)
MONDAY = datetime(2026, 8, 3, 12)


class TestWeekendLiveExecutionGate(unittest.TestCase):

    def test_default_disables_weekend_live(self):
        with (
            patch.object(mt5_signal_bot, "_active_profile", "test"),
            patch.object(mt5_signal_bot, "load_profile_config", return_value={}),
        ):
            self.assertFalse(_signal_live_weekends_enabled())
            self.assertEqual(get_live_target_hours(SATURDAY), [])
            self.assertEqual(get_live_target_hours(SUNDAY), [])

    def test_explicit_flag_enables_weekend_live(self):
        with (
            patch.object(mt5_signal_bot, "_active_profile", "test"),
            patch.object(mt5_signal_bot, "load_profile_config", return_value={"signal_live_weekends": True}),
        ):
            self.assertTrue(_signal_live_weekends_enabled())
            self.assertEqual(get_live_target_hours(SATURDAY), list(TARGET_HOURS))
            self.assertEqual(get_live_target_hours(SUNDAY), list(TARGET_HOURS))

    def test_weekdays_are_always_live(self):
        with (
            patch.object(mt5_signal_bot, "_active_profile", "test"),
            patch.object(mt5_signal_bot, "load_profile_config", return_value={}),
        ):
            self.assertEqual(get_live_target_hours(MONDAY), list(TARGET_HOURS))

    def test_schedule_orders_skips_weekend_when_disabled(self):
        result = {"signal": "BUY", "pair_dirs": {"XAUUSD": "BUY"}}
        with (
            patch.object(mt5_signal_bot, "_signal_live_weekends_enabled", return_value=False),
            patch.object(mt5_signal_bot, "_get_signal_execution_gateway") as gateway,
        ):
            keys = schedule_orders_for_signal(result, SATURDAY, 7)
            self.assertEqual(keys, [])
            gateway.return_value.schedule_signal.assert_not_called()

    def test_schedule_orders_allows_weekend_when_enabled(self):
        result = {"signal": "BUY", "pair_dirs": {"XAUUSD": "BUY"}}
        with (
            patch.object(mt5_signal_bot, "_signal_live_weekends_enabled", return_value=True),
            patch.object(mt5_signal_bot, "_get_signal_execution_gateway") as gateway,
        ):
            gateway.return_value.schedule_signal.return_value = ["k1"]
            keys = schedule_orders_for_signal(result, SATURDAY, 7)
            self.assertEqual(keys, ["k1"])
            gateway.return_value.schedule_signal.assert_called_once()

    def test_schedule_orders_always_runs_on_weekdays(self):
        result = {"signal": "SELL", "pair_dirs": {"XAUUSD": "SELL"}}
        with (
            patch.object(mt5_signal_bot, "_signal_live_weekends_enabled", return_value=False),
            patch.object(mt5_signal_bot, "_get_signal_execution_gateway") as gateway,
        ):
            gateway.return_value.schedule_signal.return_value = ["k1"]
            keys = schedule_orders_for_signal(result, MONDAY, 9)
            self.assertEqual(keys, ["k1"])
            gateway.return_value.schedule_signal.assert_called_once()


if __name__ == "__main__":
    unittest.main()
