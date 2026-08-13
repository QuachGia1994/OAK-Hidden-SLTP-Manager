"""Integrity-gated history rebuild contracts for the current MT5 provider.

Legacy MT4 persisted-store tests were retired because that source contract no
longer exists. Current MT5 market-data and H49 behavior is covered by the
provider and signal suites.
"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import mt5_signal_bot


class HistoricalOffsetProvider:
    """Provider whose live health is stale/disconnected but whose historical
    per-date offset is verified — the exact offline-rebuild scenario."""

    name = "MT5"

    def __init__(self, offset, verified_dates):
        self._offset = offset
        self._verified = set(verified_dates)

    def get_health(self):
        return SimpleNamespace(fresh=False, clock_verified=False, state="disconnected")

    def get_broker_utc_offset(self, broker_date=None):
        return self._offset

    def is_broker_utc_offset_verified(self, broker_date=None):
        return str(broker_date) in self._verified


class HistoryRecordLocalTimeTests(unittest.TestCase):
    def test_history_record_local_time_uses_historical_offset_not_live_health(self):
        provider = HistoricalOffsetProvider(offset=3, verified_dates={"2026-07-31"})
        with (
            patch.object(mt5_signal_bot, "MARKET_DATA_PROVIDER", provider),
            patch.object(mt5_signal_bot, "get_current_prices", return_value={}),
        ):
            record = mt5_signal_bot._format_signal_record(
                7, datetime(2026, 7, 31, 7), "BUY", "07:49",
                {"XAUUSD": "BUY", "GBPUSD": "BUY"}, "H7",
            )

        # Live health is stale, but the 2026-07-31 historical offset (+3) is
        # verified, so local times must still be emitted.
        self.assertIs(record["broker_clock_verified"], True)
        self.assertEqual(record["broker_utc_offset"], 3)
        self.assertEqual(record["signal_time_local"], "11:00")
        self.assertEqual(record["entry_time_local"], "11:49")
        self.assertEqual(record["signal_at_utc"], "2026-07-31T04:00:00+00:00")

    def test_history_record_hides_local_time_when_historical_offset_unverified(self):
        provider = HistoricalOffsetProvider(offset=3, verified_dates=set())
        with (
            patch.object(mt5_signal_bot, "MARKET_DATA_PROVIDER", provider),
            patch.object(mt5_signal_bot, "get_current_prices", return_value={}),
        ):
            record = mt5_signal_bot._format_signal_record(
                7, datetime(2026, 7, 31, 7), "BUY", "07:49",
                {"XAUUSD": "BUY", "GBPUSD": "BUY"}, "H7",
            )

        self.assertIs(record["broker_clock_verified"], False)
        self.assertIsNone(record["signal_time_local"])
        self.assertIsNone(record["entry_time_local"])


class WaitReasonIntegrityTests(unittest.TestCase):
    def test_wait_requires_reason(self):
        bare = {
            "date": "2026-07-31",
            "hour": 7,
            "applicable_pairs": ["XAUUSD", "GBPUSD", "GBPJPY"],
            "pair_dirs": {"XAUUSD": "WAIT", "GBPUSD": "WAIT", "GBPJPY": "WAIT"},
            "wait_reasons": {"XAUUSD": "H49_H1_MISSING", "GBPJPY": "H49_H1_MISSING"},
        }
        with self.assertRaises(mt5_signal_bot.RebuildIntegrityError):
            mt5_signal_bot._assert_wait_reasons_present(bare)

        complete = dict(bare, wait_reasons={
            "XAUUSD": "H49_H1_MISSING",
            "GBPUSD": "H49_H1_DOJI",
            "GBPJPY": "H49_H1_MISSING",
        })
        mt5_signal_bot._assert_wait_reasons_present(complete)

    def test_wait_missing_input_marks_rebuild_incomplete(self):
        missing = {
            "rebuild_state": "READY",
            "pair_signal_states": {"XAUUSD": "WAIT", "GBPUSD": "WAIT", "GBPJPY": "WAIT"},
            "wait_reasons": {"XAUUSD": "H49_H1_MISSING", "GBPUSD": "D_H4_MISSING", "GBPJPY": "WAIT_MT5_DATA"},
        }
        self.assertFalse(mt5_signal_bot._compute_rebuild_complete([missing]))

        doji = {
            "rebuild_state": "READY",
            "pair_signal_states": {"XAUUSD": "WAIT", "GBPUSD": "WAIT", "GBPJPY": "WAIT"},
            "wait_reasons": {"XAUUSD": "H49_H1_DOJI", "GBPUSD": "H49_H1_DOJI", "GBPJPY": "NOT_APPLICABLE"},
        }
        self.assertTrue(mt5_signal_bot._compute_rebuild_complete([doji]))

        d_snapshot_missing = {
            "rebuild_state": "REBUILD_INCOMPLETE",
            "rebuild_state_reason": "D_SNAPSHOT_NOT_PUBLISHED",
            "pair_signal_states": {},
        }
        self.assertFalse(mt5_signal_bot._compute_rebuild_complete([d_snapshot_missing]))

    def test_wait_reasons_are_attached_by_build_record(self):
        with patch.object(mt5_signal_bot, "evaluate_all_pairs_for_slot", return_value={
            "signal": "WAIT",
            "entry_time": None,
            "source_date": "2026-07-31",
            "applicable_pairs": ["XAUUSD", "GBPUSD"],
            "pair_dirs": {"XAUUSD": "WAIT", "GBPUSD": "WAIT"},
            "pair_signal_states": {"XAUUSD": "WAIT", "GBPUSD": "WAIT"},
            "pair_evidence": {},
            "failure_reason": "WAIT_MT5_DATA",
            "d_directions": {},
            "timing": {},
        }) as evaluate:
            record, _ = mt5_signal_bot._build_rebuild_record(datetime(2026, 7, 31, 7), 7)

        self.assertEqual(evaluate.call_count, 1)
        self.assertEqual(record["wait_reasons"]["XAUUSD"], "WAIT_MT5_DATA")


class DSnapshotPublishGateTests(unittest.TestCase):
    def test_d_snapshot_required_before_signal_publish(self):
        today = datetime(2026, 7, 22, 9, 25)

        def build_record(_broker_dt, hour, **kwargs):
            return {
                "date": "2026-07-22",
                "hour": hour,
                "signal": "BUY",
                "pair_dirs": {"XAUUSD": "BUY", "GBPUSD": "BUY"},
                "pair_signal_states": {"XAUUSD": "READY", "GBPUSD": "READY"},
                "entry_state": "READY",
                "entry_time": "07:49",
                "pair_evidence": {},
                "logic_version": mt5_signal_bot.SIGNAL_LOGIC_VERSION,
            }, {}

        with tempfile.TemporaryDirectory() as temp_dir:
            signal_log = Path(temp_dir) / "signals_log.json"
            signal_log.write_text("[]", encoding="utf-8")
            with (
                patch.object(mt5_signal_bot, "_SIGNALS_LOG", str(signal_log)),
                patch.object(mt5_signal_bot, "get_broker_time", return_value=today),
                patch.object(mt5_signal_bot, "is_slot_ready", return_value=True),
                patch.object(mt5_signal_bot, "warm_m30_history"),
                patch.object(mt5_signal_bot, "calculate_all_d_directions", return_value={"XAUUSD": {}}),
                patch.object(mt5_signal_bot, "build_d_direction_snapshot_for_date", return_value={"symbols": {}}),
                patch.object(mt5_signal_bot, "snapshot_is_publishable", return_value=False),
                patch.object(mt5_signal_bot, "_build_rebuild_record", side_effect=build_record),
            ):
                mt5_signal_bot._LAST_REBUILD_COMPLETE = True
                count = mt5_signal_bot.rebuild_recent_history(days=1)

            self.assertGreater(count, 0)
            self.assertFalse(mt5_signal_bot._LAST_REBUILD_COMPLETE)
            records = json.loads(signal_log.read_text(encoding="utf-8"))
            self.assertTrue(records)
            for rec in records:
                self.assertEqual(rec["rebuild_state"], "REBUILD_INCOMPLETE")
                self.assertEqual(rec["rebuild_state_reason"], "D_SNAPSHOT_NOT_PUBLISHED")

    def test_publishable_d_snapshot_allows_ready_slots(self):
        today = datetime(2026, 7, 22, 9, 25)

        def build_record(_broker_dt, hour, **kwargs):
            return {
                "date": "2026-07-22",
                "hour": hour,
                "signal": "BUY",
                "pair_dirs": {"XAUUSD": "BUY", "GBPUSD": "BUY"},
                "pair_signal_states": {"XAUUSD": "READY", "GBPUSD": "READY"},
                "entry_state": "READY",
                "entry_time": "07:49",
                "pair_evidence": {},
                "logic_version": mt5_signal_bot.SIGNAL_LOGIC_VERSION,
            }, {}

        with tempfile.TemporaryDirectory() as temp_dir:
            signal_log = Path(temp_dir) / "signals_log.json"
            signal_log.write_text("[]", encoding="utf-8")
            with (
                patch.object(mt5_signal_bot, "_SIGNALS_LOG", str(signal_log)),
                patch.object(mt5_signal_bot, "get_broker_time", return_value=today),
                patch.object(mt5_signal_bot, "is_slot_ready", return_value=True),
                patch.object(mt5_signal_bot, "warm_m30_history"),
                patch.object(mt5_signal_bot, "calculate_all_d_directions", return_value={"XAUUSD": {}}),
                patch.object(mt5_signal_bot, "build_d_direction_snapshot_for_date", return_value={"symbols": {}}),
                patch.object(mt5_signal_bot, "snapshot_is_publishable", return_value=True),
                patch.object(mt5_signal_bot, "_build_rebuild_record", side_effect=build_record),
            ):
                mt5_signal_bot._LAST_REBUILD_COMPLETE = False
                count = mt5_signal_bot.rebuild_recent_history(days=1)

            self.assertGreater(count, 0)
            self.assertTrue(mt5_signal_bot._LAST_REBUILD_COMPLETE)
            records = json.loads(signal_log.read_text(encoding="utf-8"))
            for rec in records:
                self.assertEqual(rec["rebuild_state"], "READY")


if __name__ == "__main__":
    unittest.main()
