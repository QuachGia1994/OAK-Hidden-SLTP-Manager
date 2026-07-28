"""Regression tests for the single startup history rebuild."""

import tempfile
import unittest
import json
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

        self.assertEqual(rebuilt_hours, [3, 4, 6, 9, 12, 14, 16])
        self.assertEqual(count, 7)

    def test_rebuild_drops_malformed_rows_without_preserving_stale_window(self):
        today = datetime(2026, 7, 22, 9, 25)
        retained = {"date": "2026-07-20", "hour": 9, "pair_dirs": {"XAUUSD": "BUY"}}
        rows = [
            retained,
            {"date": today.date().isoformat(), "hour": 5},
            {"date": today.date().isoformat(), "hour": "bad"},
            "not-a-record",
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            signal_log = Path(temp_dir) / "signals_log.json"
            signal_log.write_text(json.dumps(rows), encoding="utf-8")
            with (
                patch.object(mt5_signal_bot, "mt5_ready", True),
                patch.object(mt5_signal_bot, "_SIGNALS_LOG", str(signal_log)),
                patch.object(mt5_signal_bot, "get_broker_time", return_value=today),
                patch.object(mt5_signal_bot, "is_slot_ready", return_value=True),
                patch.object(mt5_signal_bot, "rebuild_slot_signal", return_value=False),
            ):
                mt5_signal_bot.rebuild_recent_history(days=1)

            self.assertEqual(json.loads(signal_log.read_text(encoding="utf-8")), [retained])


if __name__ == "__main__":
    unittest.main()
