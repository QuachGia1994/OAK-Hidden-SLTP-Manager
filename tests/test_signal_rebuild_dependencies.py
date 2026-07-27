"""Regression tests for the single startup history rebuild."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import mt5_signal_bot


class SignalRebuildDependencyTests(unittest.TestCase):
    def test_startup_rebuild_uses_45_calendar_days(self):
        with patch.object(mt5_signal_bot, "rebuild_recent_history", return_value=1) as rebuild:
            self.assertEqual(mt5_signal_bot.rebuild_signals_on_startup(), 1)

        rebuild.assert_called_once_with(days=45)

    def test_current_day_rebuild_visits_only_active_slots(self):
        rebuilt_hours = []

        def rebuild(_broker_dt, hour):
            rebuilt_hours.append(hour)
            return True

        with tempfile.TemporaryDirectory() as temp_dir:
            signal_log = Path(temp_dir) / "signals_log.json"
            signal_log.write_text("[]", encoding="utf-8")
            with (
                patch.object(mt5_signal_bot, "mt5_ready", True),
                patch.object(mt5_signal_bot, "_SIGNALS_LOG", str(signal_log)),
                patch.object(mt5_signal_bot, "get_broker_time", return_value=datetime(2026, 7, 22, 9, 25)),
                patch.object(mt5_signal_bot, "is_slot_ready", return_value=True),
                patch.object(mt5_signal_bot, "rebuild_slot_signal", side_effect=rebuild),
            ):
                count = mt5_signal_bot.rebuild_recent_history(days=1)

        self.assertEqual(rebuilt_hours, [3, 4, 5, 6, 12, 16])
        self.assertEqual(count, 6)


if __name__ == "__main__":
    unittest.main()
