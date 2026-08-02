"""Integrity-gated history rebuild: local time, WAIT reasons, D snapshot, D-H4,
H49 source, and the history rebuild worker.

Mirrors the acceptance tests required by the round-3 prompt:
- test_history_record_local_time_uses_historical_offset_not_live_health
- test_wait_requires_reason
- test_wait_missing_input_marks_rebuild_incomplete
- test_d_snapshot_required_before_signal_publish
- test_d_h4_exact_2000_lookup
- test_d_h4_missing_lists_candidates
- test_h49_h1_uses_active_or_single_offline_source
- test_history_worker_runs_without_feed_connected
- test_history_worker_does_not_clear_on_incomplete_rebuild
"""
import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot
import history_rebuild_worker
from repositories.mt4_feed_store import MT4FeedStore


def _new_store():
    handle, db_path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    return MT4FeedStore(db_path=db_path), db_path


def _seed_bar(store, source_id, symbol, timeframe, broker_open_at, ohlc, utc_open_at=None):
    store.save_bars(source_id, symbol, symbol, timeframe, [{
        "broker_open_at": broker_open_at,
        "broker_close_at": (datetime.fromisoformat(broker_open_at) + timedelta(hours=1 if timeframe == "H1" else 4)).strftime("%Y-%m-%d %H:%M:%S"),
        "open": ohlc[0], "high": ohlc[1], "low": ohlc[2], "close": ohlc[3],
        "utc_open_at": utc_open_at,
        "tick_volume": 10,
        "is_complete": True,
    }])


class HistoricalOffsetProvider:
    """Provider whose live health is stale/disconnected but whose historical
    per-date offset is verified — the exact offline-rebuild scenario."""

    name = "MT4"

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


class DH4LookupTests(unittest.TestCase):
    def test_d_h4_exact_2000_lookup(self):
        store, db_path = _new_store()
        try:
            target_date = datetime(2026, 8, 3).date()
            session_date = target_date - timedelta(days=1)
            _seed_bar(
                store, "ea_test", "XAUUSD", "H4",
                f"{session_date} 20:00:00",
                ("2400.00", "2410.00", "2395.00", "2405.00"),
                utc_open_at=f"{session_date} 17:00:00+00:00",
            )
            provider = mt5_signal_bot.MT4FeedProvider(feed_store=store)

            candle, session, offset, ambiguous = (
                mt5_signal_bot.find_previous_session_h4_20_candle(
                    "XAUUSD", target_date, market_data_provider=provider
                )
            )

            self.assertIsNotNone(candle)
            self.assertEqual(session, session_date)
            self.assertEqual(offset, 3)
            self.assertFalse(ambiguous)
            self.assertEqual(candle["broker_dt"].replace(tzinfo=None), datetime(session_date.year, session_date.month, session_date.day, 20, 0))
        finally:
            store.close()
            os.unlink(db_path)

    def test_d_h4_missing_lists_candidates(self):
        store, db_path = _new_store()
        try:
            target_date = datetime(2026, 8, 3).date()
            session_date = target_date - timedelta(days=1)
            _seed_bar(
                store, "ea_test", "XAUUSD", "H4",
                f"{session_date} 21:00:00",
                ("2400.00", "2410.00", "2395.00", "2405.00"),
                utc_open_at=f"{session_date} 18:00:00+00:00",
            )
            provider = mt5_signal_bot.MT4FeedProvider(feed_store=store)
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                candle, session, _offset, ambiguous = (
                    mt5_signal_bot.find_previous_session_h4_20_candle(
                        "XAUUSD", target_date, market_data_provider=provider
                    )
                )

            self.assertIsNone(candle)
            self.assertFalse(ambiguous)
            log = buffer.getvalue()
            self.assertIn("[D-H4] DIAGNOSTICS", log)
            self.assertIn("near-miss 21:00", log)
            self.assertIn(f"{session_date}T21:00:00", log)
        finally:
            store.close()
            os.unlink(db_path)

    def test_d_h4_ambiguous_sources_fail_closed(self):
        store, db_path = _new_store()
        try:
            target_date = datetime(2026, 8, 3).date()
            session_date = target_date - timedelta(days=1)
            _seed_bar(
                store, "ea_a", "XAUUSD", "H4",
                f"{session_date} 20:00:00",
                ("2400.00", "2410.00", "2395.00", "2405.00"),
                utc_open_at=f"{session_date} 17:00:00+00:00",
            )
            _seed_bar(
                store, "ea_b", "XAUUSD", "H4",
                f"{session_date} 20:00:00",
                ("2390.00", "2399.00", "2385.00", "2392.00"),
                utc_open_at=f"{session_date} 17:00:00+00:00",
            )
            provider = mt5_signal_bot.MT4FeedProvider(feed_store=store)

            candle, session, _offset, ambiguous = (
                mt5_signal_bot.find_previous_session_h4_20_candle(
                    "XAUUSD", target_date, market_data_provider=provider
                )
            )
            self.assertIsNone(candle)
            self.assertTrue(ambiguous)

            evidence = mt5_signal_bot._compute_d_from_source(
                "XAUUSD", "XAUUSD", target_date, market_data_provider=provider
            )
            self.assertEqual(evidence["d_state"], "AMBIGUOUS_H4_20")
        finally:
            store.close()
            os.unlink(db_path)


class H49SourceFilteringTests(unittest.TestCase):
    def test_h49_h1_uses_active_or_single_offline_source(self):
        from domain.signal_v87 import evaluate_h49_reference_signal

        store, db_path = _new_store()
        try:
            slot_dt = datetime(2026, 8, 3, 7)
            _seed_bar(
                store, "ea_test", "XAUUSD", "H1",
                f"{slot_dt - timedelta(hours=1):%Y-%m-%d %H:%M:%S}",
                ("100", "100", "99", "99"),  # GIAM
                utc_open_at="2026-08-03T03:00:00+00:00",
            )
            provider = mt5_signal_bot.MT4FeedProvider(feed_store=store)
            self.assertIsNone(provider.get_active_source_id())

            result = evaluate_h49_reference_signal(slot_dt, provider, as_of=slot_dt + timedelta(minutes=30))

            self.assertEqual(result["state"], "READY")
            self.assertEqual(result["candle_direction"], "GIAM")
            self.assertEqual(result["reversed_signal"], "BUY")
            self.assertIsNone(result["failure_reason"])
        finally:
            store.close()
            os.unlink(db_path)

    def test_h49_h1_ambiguous_sources_fail_closed(self):
        from domain.signal_v87 import evaluate_h49_reference_signal

        store, db_path = _new_store()
        try:
            slot_dt = datetime(2026, 8, 3, 7)
            _seed_bar(
                store, "ea_a", "XAUUSD", "H1",
                f"{slot_dt - timedelta(hours=1):%Y-%m-%d %H:%M:%S}",
                ("100", "100", "99", "99"),
                utc_open_at="2026-08-03T03:00:00+00:00",
            )
            _seed_bar(
                store, "ea_b", "XAUUSD", "H1",
                f"{slot_dt - timedelta(hours=1):%Y-%m-%d %H:%M:%S}",
                ("200", "200", "199", "199"),
                utc_open_at="2026-08-03T03:00:00+00:00",
            )
            provider = mt5_signal_bot.MT4FeedProvider(feed_store=store)

            result = evaluate_h49_reference_signal(slot_dt, provider, as_of=slot_dt + timedelta(minutes=30))

            self.assertEqual(result["state"], "WAIT")
            self.assertEqual(result["failure_reason"], "H49_H1_AMBIGUOUS")
            self.assertEqual(result["reversed_signal"], "WAIT")
        finally:
            store.close()
            os.unlink(db_path)


class HistoryRebuildWorkerTests(unittest.TestCase):
    def test_history_worker_runs_without_feed_connected(self):
        store, db_path = _new_store()
        try:
            _seed_bar(
                store, "ea_test", "XAUUSD", "M30", "2026-07-31 20:30:00",
                ("1", "1", "1", "1"), utc_open_at="2026-07-31T13:30:00+00:00",
            )
            calls = []

            def fake_rebuild(days):
                calls.append(days)

            worker = history_rebuild_worker.HistoryRebuildWorker(store=store, rebuild_fn=fake_rebuild)
            self.assertIsNone(store.get_latest_heartbeat())
            self.assertIsNone(store.get_active_source_id(max_age_seconds=60))
            self.assertTrue(worker.should_run())
            worker.run_once()
            self.assertEqual(calls, [history_rebuild_worker.HISTORY_REBUILD_DAYS])
            self.assertFalse(worker.should_run())
        finally:
            store.close()
            os.unlink(db_path)

    def test_history_worker_does_not_clear_on_incomplete_rebuild(self):
        store, db_path = _new_store()
        try:
            _seed_bar(
                store, "ea_test", "XAUUSD", "M30", "2026-07-31 20:30:00",
                ("1", "1", "1", "1"), utc_open_at="2026-07-31T13:30:00+00:00",
            )
            with tempfile.TemporaryDirectory() as temp_dir:
                signal_log = Path(temp_dir) / "signals_log.json"
                retained = {"date": "2026-07-20", "hour": 9, "signal": "BUY", "pair_dirs": {"XAUUSD": "BUY"}}
                signal_log.write_text(json.dumps([retained]), encoding="utf-8")

                def incomplete_rebuild(days):
                    mt5_signal_bot._LAST_REBUILD_COMPLETE = False

                worker = history_rebuild_worker.HistoryRebuildWorker(store=store, rebuild_fn=incomplete_rebuild)
                ran = worker.run_once()
                self.assertTrue(ran)
                self.assertFalse(worker._last_rebuild_complete)

                records = json.loads(signal_log.read_text(encoding="utf-8"))
                self.assertEqual(records, [retained])

                def complete_rebuild(days):
                    mt5_signal_bot._LAST_REBUILD_COMPLETE = True

                worker2 = history_rebuild_worker.HistoryRebuildWorker(store=store, rebuild_fn=complete_rebuild)
                worker2._last_seen = None
                worker2.run_once()
                self.assertTrue(worker2._last_rebuild_complete)
        finally:
            store.close()
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
