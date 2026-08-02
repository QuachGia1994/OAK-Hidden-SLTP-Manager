"""v88 weekend-capable 24/7 rebuild: Sat/Sun slots are rebuilt, never skipped."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot
from mt5_signal_bot import (
    TARGET_HOURS,
    get_live_target_hours,
    get_rebuild_target_hours,
    rebuild_recent_history,
    rebuild_slot_signal,
)

SATURDAY = datetime(2026, 8, 1, 12)
SUNDAY = datetime(2026, 8, 2, 12)
FRIDAY = datetime(2026, 7, 31, 12)


class TestWeekendHistoryRebuild(unittest.TestCase):

    def test_get_rebuild_target_hours_includes_weekends(self):
        self.assertEqual(get_rebuild_target_hours(SATURDAY, include_weekends=True), list(TARGET_HOURS))
        self.assertEqual(get_rebuild_target_hours(SUNDAY, include_weekends=True), list(TARGET_HOURS))
        self.assertEqual(get_rebuild_target_hours(FRIDAY, include_weekends=False), list(TARGET_HOURS))

    def test_get_rebuild_target_hours_skips_weekends_by_default(self):
        self.assertEqual(get_rebuild_target_hours(SATURDAY), [])
        self.assertEqual(get_rebuild_target_hours(SUNDAY), [])
        self.assertEqual(get_rebuild_target_hours(SATURDAY, weekday=6), [])

    def test_live_target_hours_never_include_weekends(self):
        # Default profile: weekends disabled.
        self.assertEqual(get_live_target_hours(SATURDAY), [])
        self.assertEqual(get_live_target_hours(SUNDAY), [])

    def test_rebuild_slot_signal_accepts_weekend_when_include_weekends(self):
        slot_dt = SATURDAY.replace(hour=7, minute=0, second=0, microsecond=0)
        record = {
            "date": slot_dt.date().isoformat(),
            "hour": 7,
            "signal": "BUY",
            "logic_version": 88,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            signal_log = Path(temp_dir) / "signals_log.json"
            with (
                patch.object(mt5_signal_bot, "_SIGNALS_LOG", str(signal_log)),
                patch.object(mt5_signal_bot, "_build_rebuild_record", return_value=(record, {})),
            ):
                ok = rebuild_slot_signal(slot_dt, 7, as_of_dt=slot_dt + timedelta(days=1), include_weekends=True)
                self.assertTrue(ok)
                written = __import__("json").loads(signal_log.read_text(encoding="utf-8"))
                self.assertEqual(written[0]["date"], slot_dt.date().isoformat())

    def test_rebuild_slot_signal_skips_weekend_without_include_weekends(self):
        slot_dt = SUNDAY.replace(hour=14, minute=0, second=0, microsecond=0)
        with (
            patch.object(mt5_signal_bot, "_build_rebuild_record") as build,
        ):
            ok = rebuild_slot_signal(slot_dt, 14, include_weekends=False)
            self.assertFalse(ok)
            build.assert_not_called()

    def test_rebuild_recent_history_forwards_weekend_flag(self):
        monday = datetime(2026, 8, 3, 12)
        with (
            patch.object(mt5_signal_bot, "get_broker_time", return_value=monday),
            patch.object(mt5_signal_bot, "warm_m30_history") as warm,
            patch.object(mt5_signal_bot, "get_rebuild_target_hours", return_value=[7]) as target,
            patch.object(mt5_signal_bot, "_build_rebuild_record", side_effect=lambda *a, **k: (None, {})),
            patch.object(mt5_signal_bot, "_write_signals_log_atomic") as write,
        ):
            rebuilt = rebuild_recent_history(days=4, include_weekends=True)
            self.assertEqual(rebuilt, 0)
            # Weekend dates must reach the target-hours resolution path.
            weekend_args = [call.args[0] for call in target.call_args_list if call.args[0].weekday() >= 5]
            self.assertGreater(len(weekend_args), 0)


if __name__ == "__main__":
    unittest.main()
