"""Regression tests for safe history rebuild — atomic per-record merge, zero-valid-candidates fail-safe."""

import tempfile
import unittest
import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import mt5_signal_bot


class HistorySafeRebuildTests(unittest.TestCase):
    """Verify rebuild_recent_history performs atomic per-record merge, not per-date deletion."""

    def test_rebuild_replaces_only_matching_key(self):
        """When a new candidate has the same (date, hour) as an existing record, the old one is replaced."""
        today = datetime(2026, 7, 22, 9, 25)
        existing_old = {
            "date": "2026-07-20",
            "hour": 9,
            "signal": "BUY",
            "pair_dirs": {"XAUUSD": "BUY", "GBPUSD": "BUY"},
            "entry_state": "READY",
            "entry_time": "07:49",
            "logic_version": 87,
            "pair_evidence": {},
        }
        existing_other = {
            "date": "2026-07-20",
            "hour": 12,
            "signal": "SELL",
            "pair_dirs": {"XAUUSD": "SELL", "GBPUSD": "SELL"},
            "entry_state": "READY",
            "entry_time": "11:50",
            "logic_version": 87,
            "pair_evidence": {},
        }
        new_candidate = {
            "date": "2026-07-20",
            "hour": 9,
            "signal": "SELL",
            "pair_dirs": {"XAUUSD": "SELL", "GBPUSD": "SELL"},
            "entry_state": "READY",
            "entry_time": "07:55",
            "logic_version": 88,
            "pair_evidence": {},
        }

        def build_record(_broker_dt, hour, **kwargs):
            if hour == 9:
                return new_candidate, None
            return None, "skip"

        with tempfile.TemporaryDirectory() as temp_dir:
            signal_log = Path(temp_dir) / "signals_log.json"
            signal_log.write_text(json.dumps([existing_old, existing_other]), encoding="utf-8")
            with (
                patch.object(mt5_signal_bot, "mt5_ready", True),
                patch.object(mt5_signal_bot, "_SIGNALS_LOG", str(signal_log)),
                patch.object(mt5_signal_bot, "get_broker_time", return_value=today),
                patch.object(mt5_signal_bot, "is_slot_ready", return_value=True),
                patch.object(mt5_signal_bot, "_build_rebuild_record", side_effect=build_record),
                patch.object(mt5_signal_bot, "warm_m30_history"),
            ):
                count = mt5_signal_bot.rebuild_recent_history(days=1)

            records = json.loads(signal_log.read_text(encoding="utf-8"))

        # Hour 12 record must survive untouched; hour 9 replaced with new candidate
        dates_and_hours = [(r["date"], r["hour"]) for r in records]
        self.assertIn(("2026-07-20", 12), dates_and_hours)
        hour9 = [r for r in records if r["date"] == "2026-07-20" and r["hour"] == 9]
        self.assertEqual(len(hour9), 1)
        self.assertEqual(hour9[0]["logic_version"], 88)
        self.assertEqual(hour9[0]["signal"], "SELL")

    def test_rebuild_preserves_existing_when_build_record_returns_none(self):
        """When _build_rebuild_record returns None for a slot, the existing record (if any) is preserved."""
        today = datetime(2026, 7, 22, 9, 25)
        existing = {
            "date": "2026-07-20",
            "hour": 9,
            "signal": "BUY",
            "pair_dirs": {"XAUUSD": "BUY", "GBPUSD": "BUY"},
            "entry_state": "READY",
            "entry_time": "07:49",
            "logic_version": 87,
            "pair_evidence": {},
        }

        def build_record(_broker_dt, hour, **kwargs):
            return None, "no_data"

        with tempfile.TemporaryDirectory() as temp_dir:
            signal_log = Path(temp_dir) / "signals_log.json"
            signal_log.write_text(json.dumps([existing]), encoding="utf-8")
            with (
                patch.object(mt5_signal_bot, "mt5_ready", True),
                patch.object(mt5_signal_bot, "_SIGNALS_LOG", str(signal_log)),
                patch.object(mt5_signal_bot, "get_broker_time", return_value=today),
                patch.object(mt5_signal_bot, "is_slot_ready", return_value=True),
                patch.object(mt5_signal_bot, "_build_rebuild_record", side_effect=build_record),
                patch.object(mt5_signal_bot, "warm_m30_history"),
            ):
                count = mt5_signal_bot.rebuild_recent_history(days=1)

            records = json.loads(signal_log.read_text(encoding="utf-8"))

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["logic_version"], 87)
        self.assertEqual(records[0]["signal"], "BUY")

    def test_zero_valid_candidates_aborts_and_preserves_all(self):
        """When all candidates fail validation, the existing history must NOT be touched."""
        today = datetime(2026, 7, 22, 9, 25)
        existing = {
            "date": "2026-07-20",
            "hour": 9,
            "signal": "BUY",
            "pair_dirs": {"XAUUSD": "BUY", "GBPUSD": "BUY"},
            "entry_state": "READY",
            "entry_time": "07:49",
            "logic_version": 87,
            "pair_evidence": {},
        }
        # Malformed candidate — no pair_dirs
        bad_candidate = {
            "date": "2026-07-20",
            "hour": 9,
            "signal": "BUY",
            "entry_state": "READY",
            "logic_version": 88,
        }

        def build_record(_broker_dt, hour, **kwargs):
            return bad_candidate, None

        with tempfile.TemporaryDirectory() as temp_dir:
            signal_log = Path(temp_dir) / "signals_log.json"
            signal_log.write_text(json.dumps([existing]), encoding="utf-8")
            with (
                patch.object(mt5_signal_bot, "mt5_ready", True),
                patch.object(mt5_signal_bot, "_SIGNALS_LOG", str(signal_log)),
                patch.object(mt5_signal_bot, "get_broker_time", return_value=today),
                patch.object(mt5_signal_bot, "is_slot_ready", return_value=True),
                patch.object(mt5_signal_bot, "_build_rebuild_record", side_effect=build_record),
                patch.object(mt5_signal_bot, "warm_m30_history"),
            ):
                count = mt5_signal_bot.rebuild_recent_history(days=1)

            records = json.loads(signal_log.read_text(encoding="utf-8"))

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["logic_version"], 87)


if __name__ == "__main__":
    unittest.main()
