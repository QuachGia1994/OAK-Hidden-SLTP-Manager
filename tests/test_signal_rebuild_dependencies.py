"""Regression tests for dependency-aware current-day history rebuilds."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import mt5_signal_bot


class SignalRebuildDependencyTests(unittest.TestCase):
    def test_today_rechecks_h7_h8_after_rebuilding_h5(self):
        rebuilt_hours = []

        def is_ready(_broker_dt, hour):
            return hour in (4, 5) or (hour in (7, 8) and 5 in rebuilt_hours)

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
                patch.object(mt5_signal_bot, "get_target_hours", return_value=[4, 5, 7, 8]),
                patch.object(mt5_signal_bot, "is_slot_ready", side_effect=is_ready),
                patch.object(mt5_signal_bot, "rebuild_slot_signal", side_effect=rebuild),
            ):
                count = mt5_signal_bot.rebuild_recent_history(days=1)

        self.assertEqual(rebuilt_hours, [4, 5, 7, 8])
        self.assertEqual(count, 4)


if __name__ == "__main__":
    unittest.main()
