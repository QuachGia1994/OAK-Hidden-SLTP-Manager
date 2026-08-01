"""Regression tests for the single startup history rebuild."""

import tempfile
import unittest
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot


class SignalRebuildDependencyTests(unittest.TestCase):
    def test_startup_rebuild_uses_45_calendar_days(self):
        with patch.object(mt5_signal_bot, "rebuild_recent_history", return_value=1) as rebuild:
            self.assertEqual(mt5_signal_bot.rebuild_signals_on_startup(), 1)

        rebuild.assert_called_once_with(days=45)

    def test_current_day_rebuild_visits_only_active_slots(self):
        rebuilt_hours = []

        def build_record(_broker_dt, hour, **kwargs):
            rebuilt_hours.append(hour)
            rec = {
                "date": "2026-07-22",
                "hour": hour,
                "signal": "BUY",
                "pair_dirs": {"XAUUSD": "BUY"},
                "entry_state": "READY",
                "pair_evidence": {},
                "logic_version": mt5_signal_bot.SIGNAL_LOGIC_VERSION,
            }
            return rec, None

        with tempfile.TemporaryDirectory() as temp_dir:
            signal_log = Path(temp_dir) / "signals_log.json"
            signal_log.write_text("[]", encoding="utf-8")
            with (
                patch.object(mt5_signal_bot, "mt5_ready", True),
                patch.object(mt5_signal_bot, "_SIGNALS_LOG", str(signal_log)),
                patch.object(mt5_signal_bot, "get_broker_time", return_value=datetime(2026, 7, 22, 9, 25)),
                patch.object(mt5_signal_bot, "is_slot_ready", return_value=True),
                patch.object(mt5_signal_bot, "_build_rebuild_record", side_effect=build_record),
                patch.object(mt5_signal_bot, "warm_m30_history"),
            ):
                count = mt5_signal_bot.rebuild_recent_history(days=1)

        self.assertEqual(rebuilt_hours, [3, 7, 9, 12, 14, 16])
        self.assertEqual(count, 6)

    def test_rebuild_drops_malformed_rows_without_preserving_stale_window(self):
        today = datetime(2026, 7, 22, 9, 25)
        retained = {"date": "2026-07-20", "hour": 9, "pair_dirs": {"XAUUSD": "BUY"}}
        non_active_hour = {"date": today.date().isoformat(), "hour": 5}
        rows = [
            retained,
            non_active_hour,
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
                patch.object(mt5_signal_bot, "_build_rebuild_record", return_value=(None, None)),
                patch.object(mt5_signal_bot, "warm_m30_history"),
            ):
                mt5_signal_bot.rebuild_recent_history(days=1)

            result = json.loads(signal_log.read_text(encoding="utf-8"))
            self.assertIn(retained, result)
            self.assertIn(non_active_hour, result)
            self.assertEqual(len(result), 2)

    def test_history_rebuild_uses_latest_completed_bar_when_live_clock_is_stale(self):
        anchor = datetime(2026, 7, 31, 23, 30)
        rebuilt_as_of = []

        def build_record(broker_dt, hour, **kwargs):
            rebuilt_as_of.append(kwargs["as_of_dt"])
            return {
                "date": broker_dt.date().isoformat(),
                "hour": hour,
                "signal": "SELL",
                "pair_dirs": {"XAUUSD": "SELL"},
                "logic_version": mt5_signal_bot.SIGNAL_LOGIC_VERSION,
            }, {}

        provider = SimpleNamespace(
            name="MT4",
            get_latest_completed_broker_datetime=lambda **_kwargs: anchor,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            signal_log = Path(temp_dir) / "signals_log.json"
            signal_log.write_text("[]", encoding="utf-8")
            with (
                patch.object(mt5_signal_bot, "_SIGNALS_LOG", str(signal_log)),
                patch.object(mt5_signal_bot, "MARKET_DATA_PROVIDER", provider),
                patch.object(mt5_signal_bot, "get_broker_time", side_effect=mt5_signal_bot.MarketDataClockError("stale")),
                patch.object(mt5_signal_bot, "warm_m30_history"),
                patch.object(mt5_signal_bot, "calculate_all_d_directions", return_value={}),
                patch.object(mt5_signal_bot, "is_slot_ready", return_value=True),
                patch.object(mt5_signal_bot, "_build_rebuild_record", side_effect=build_record),
            ):
                rebuilt = mt5_signal_bot.rebuild_recent_history(days=1)

        self.assertEqual(rebuilt, len(mt5_signal_bot.ACTIVE_HOURS))
        self.assertEqual(rebuilt_as_of, [anchor] * len(mt5_signal_bot.ACTIVE_HOURS))


if __name__ == "__main__":
    unittest.main()
