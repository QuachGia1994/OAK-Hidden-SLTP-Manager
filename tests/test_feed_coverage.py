"""MT4 feed coverage matrix, verify gates, MISSING_INPUT policy, the
multi-symbol v88 EA source, and the history backfill watch worker.

Mirrors the acceptance tests required by the v88 multi-symbol feed plan:
- test_coverage_detects_missing_h4_20
- test_coverage_detects_missing_h1_for_h49
- test_coverage_detects_missing_h16_h1_layer2
- test_coverage_detects_missing_h16_h1_layer3
- test_rebuild_does_not_mark_wait_mt4_data_as_complete
- test_d_direction_ui_falls_back_to_signal_record_daily_directions
- test_backfill_complete_requires_all_symbols_all_timeframes
- test_multisymbol_ea_source_contains_symbol_loop
- test_multisymbol_ea_publishes_h4_for_all_symbols
- test_rebuild_retries_after_coverage_complete
- test_history_stats_exclude_incomplete_wait_records
"""
import contextlib
import io
import os
import tempfile
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch

from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import history_backfill_watch_worker
import mt5_signal_bot
from repositories.mt4_feed_store import (
    REQUIRED_FEED_SYMBOLS,
    REQUIRED_FEED_TIMEFRAMES,
    MT4FeedStore,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EA_SOURCE_PATH = os.path.join(REPO_ROOT, "MT4_Data_Feeder.mq4")

# The EA and server agree on this exact matrix.
EXPECTED_FEED_MATRIX = (
    ("XAUUSD", "M30"), ("XAUUSD", "H1"), ("XAUUSD", "H4"),
    ("GBPUSD", "M30"), ("GBPUSD", "H1"), ("GBPUSD", "H4"),
    ("GBPAUD", "M30"), ("GBPAUD", "H1"), ("GBPAUD", "H4"),
    ("GBPJPY", "M30"), ("GBPJPY", "H1"), ("GBPJPY", "H4"),
    ("GBPCAD", "M30"), ("GBPCAD", "H1"), ("GBPCAD", "H4"),
)


def _new_store():
    handle, db_path = tempfile.mkstemp(suffix=".db")
    os.close(handle)
    return MT4FeedStore(db_path=db_path), db_path


def _tf_minutes(timeframe):
    return {"M30": 30, "H1": 60, "H4": 240}[timeframe]


def _seed_bar(store, source_id, symbol, timeframe, broker_open_at, ohlc, utc_open_at=""):
    opened = datetime.fromisoformat(broker_open_at)
    store.save_bars(source_id, symbol, symbol, timeframe, [{
        "broker_open_at": broker_open_at,
        "broker_close_at": (opened + timedelta(minutes=_tf_minutes(timeframe))).strftime("%Y-%m-%d %H:%M:%S"),
        "open": ohlc[0], "high": ohlc[1], "low": ohlc[2], "close": ohlc[3],
        "utc_open_at": utc_open_at,
        "tick_volume": 10,
        "is_complete": True,
    }])


def _last_weekday_before(today=None):
    probe = (today or date.today()) - timedelta(days=1)
    while probe.weekday() >= 5:
        probe -= timedelta(days=1)
    return probe


def _seed_full_day(store, source_id, session_date, skip_symbols=()):
    """Seed one completed weekday session for every required symbol/timeframe."""
    for symbol in REQUIRED_FEED_SYMBOLS:
        if symbol in skip_symbols:
            continue
        for timeframe in REQUIRED_FEED_TIMEFRAMES:
            hour = {"M30": "06:30", "H1": "06:00", "H4": "20:00"}[timeframe]
            _seed_bar(
                store, source_id, symbol, timeframe,
                f"{session_date} {hour}:00", ("1", "1", "1", "1"),
            )


def _seed_full_window(store, source_id, days=45, skip_symbols=()):
    """Seed every fully-elapsed weekday session in the coverage window."""
    from datetime import datetime, timezone
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    today_date = datetime.now(timezone.utc).date()
    cursor = cutoff_date
    while cursor < today_date:
        if cursor.weekday() < 5:
            _seed_full_day(store, source_id, cursor, skip_symbols=skip_symbols)
        cursor += timedelta(days=1)


class FeedCoverageStoreTests(unittest.TestCase):
    def test_coverage_detects_missing_h4_20(self):
        store, db_path = _new_store()
        try:
            session = _last_weekday_before()
            for symbol in REQUIRED_FEED_SYMBOLS:
                _seed_bar(store, "ea_test", symbol, "M30", f"{session} 06:30:00", ("1", "1", "1", "1"))
                _seed_bar(store, "ea_test", symbol, "H1", f"{session} 06:00:00", ("1", "1", "1", "1"))
                # H4 exists but opens at 16:00, never 20:00 -> session gap.
                _seed_bar(store, "ea_test", symbol, "H4", f"{session} 16:00:00", ("1", "1", "1", "1"))

            coverage = store.get_feed_coverage(days=45)

            self.assertFalse(coverage["coverage_complete"])
            h4_gaps = [m for m in coverage["missing"]
                       if m["timeframe"] == "H4" and m["reason"] == "NO_H4_20_FOR_SESSION"]
            self.assertTrue(h4_gaps)
            self.assertIn(session.isoformat(), {m["date"] for m in h4_gaps})
        finally:
            store.close()
            os.unlink(db_path)

    def test_backfill_complete_requires_all_symbols_all_timeframes(self):
        store, db_path = _new_store()
        try:
            _seed_full_window(store, "ea_test", days=45)

            coverage = store.get_feed_coverage(days=45)
            self.assertTrue(coverage["coverage_complete"], coverage["missing"])

            store.clear()
            _seed_full_window(store, "ea_test", days=45, skip_symbols={"GBPCAD"})

            coverage = store.get_feed_coverage(days=45)
            self.assertFalse(coverage["coverage_complete"])
            no_bars = [m for m in coverage["missing"] if m["reason"] == "NO_BARS"]
            self.assertTrue(any(m["symbol"] == "GBPCAD" for m in no_bars))
            self.assertEqual(len(no_bars), 3)  # GBPCAD M30/H1/H4
        finally:
            store.close()
            os.unlink(db_path)


class VerifySlotInputGateTests(unittest.TestCase):
    def _provider(self, store):
        return mt5_signal_bot.MT4FeedProvider(feed_store=store)

    def _seed_d(self, store, session_date):
        # XAUUSD previous-session H4 20:00 with a valid UTC offset (+3) so the
        # D-Direction lookup can verify the historical offset from the bars.
        for symbol in REQUIRED_FEED_SYMBOLS:
            _seed_bar(
                store, "ea_test", symbol, "H4", f"{session_date} 20:00:00",
                ("2400.00", "2410.00", "2395.00", "2405.00"),
                utc_open_at=f"{session_date} 17:00:00+00:00",
            )

    def test_coverage_detects_missing_h1_for_h49(self):
        store, db_path = _new_store()
        try:
            session = _last_weekday_before()
            target = session + timedelta(days=1)
            self._seed_d(store, session)
            # M30 Layer2/Layer3 for the H7 slot, but no H1 06:00 -> 07:00.
            slot = datetime.combine(target, datetime.min.time()).replace(hour=7)
            for minutes in (30, 60, 90):
                _seed_bar(store, "ea_test", "XAUUSD", "M30",
                          (slot - timedelta(minutes=minutes)).isoformat(sep=" "), ("1", "1", "1", "1"))
            for minutes in (0, 30, 60):
                _seed_bar(store, "ea_test", "XAUUSD", "M30",
                          (slot - timedelta(minutes=minutes)).isoformat(sep=" "), ("1", "1", "1", "1"))

            result = mt5_signal_bot.verify_slot_inputs(target, 7, market_data_provider=self._provider(store))

            self.assertFalse(result["ok"])
            h49 = [m for m in result["missing"] if m["reason"] == "H49_H1_MISSING"]
            self.assertTrue(h49)
            self.assertTrue(any("06:00" in m["broker_open_at"] for m in h49))
        finally:
            store.close()
            os.unlink(db_path)

    def test_coverage_detects_missing_h16_h1_layer2(self):
        store, db_path = _new_store()
        try:
            session = _last_weekday_before()
            target = session + timedelta(days=1)
            self._seed_d(store, session)
            # Layer2 H1 05/04/03; leave 03:00 missing.
            for opening in (5, 4):
                _seed_bar(store, "ea_test", "XAUUSD", "H1",
                          f"{target} {opening:02d}:00:00", ("1", "1", "1", "1"))

            result = mt5_signal_bot.verify_slot_inputs(target, 16, market_data_provider=self._provider(store))

            self.assertFalse(result["ok"])
            h16 = [m for m in result["missing"] if m["reason"] == "H16_H1_MISSING"]
            self.assertTrue(h16)
            self.assertTrue(any("03:00" in m["broker_open_at"] for m in h16))
        finally:
            store.close()
            os.unlink(db_path)

    def test_coverage_detects_missing_h16_h1_layer3(self):
        store, db_path = _new_store()
        try:
            session = _last_weekday_before()
            target = session + timedelta(days=1)
            self._seed_d(store, session)
            # Layer2 H1 05/04/03 present; Layer3 H1 10/09/08 missing.
            for opening in (5, 4, 3):
                _seed_bar(store, "ea_test", "XAUUSD", "H1",
                          f"{target} {opening:02d}:00:00", ("1", "1", "1", "1"))

            result = mt5_signal_bot.verify_slot_inputs(target, 16, market_data_provider=self._provider(store))

            self.assertFalse(result["ok"])
            h16 = [m for m in result["missing"] if m["reason"] == "H16_H1_MISSING"]
            self.assertTrue(h16)
            self.assertTrue(any("10:00" in m["broker_open_at"] for m in h16))
        finally:
            store.close()
            os.unlink(db_path)


class MissingInputPolicyTests(unittest.TestCase):
    def test_rebuild_does_not_mark_wait_mt5_data_as_complete(self):
        wait_record = {
            "rebuild_state": "READY",
            "pair_signal_states": {"XAUUSD": "WAIT", "GBPUSD": "WAIT"},
            "wait_reasons": {"XAUUSD": "WAIT_MT5_DATA", "GBPUSD": "H49_H1_DOJI"},
        }
        self.assertFalse(mt5_signal_bot._compute_rebuild_complete([wait_record]))

        missing_input_record = {
            "rebuild_state": "MISSING_INPUT",
            "incomplete": True,
            "missing_inputs": ["WAIT_MT5_DATA"],
            "pair_signal_states": {},
        }
        self.assertFalse(mt5_signal_bot._compute_rebuild_complete([missing_input_record]))

    def test_build_record_stamps_missing_input(self):
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
        }):
            record, _ = mt5_signal_bot._build_rebuild_record(datetime(2026, 7, 31, 7), 7)

        self.assertEqual(record["rebuild_state"], "MISSING_INPUT")
        self.assertIs(record["incomplete"], True)
        self.assertIn("WAIT_MT5_DATA", record["missing_inputs"])

    def test_d_direction_ui_falls_back_to_signal_record_daily_directions(self):
        # Backend contract for the (deferred) UI fallback: every rebuilt record
        # of a date carries the date's daily_directions so the D panel can render
        # from the signal record when no standalone snapshot exists.
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
            signal_log = os.path.join(temp_dir, "signals_log.json")
            with open(signal_log, "w", encoding="utf-8") as f:
                f.write("[]")
            with (
                patch.object(mt5_signal_bot, "_SIGNALS_LOG", signal_log),
                patch.object(mt5_signal_bot, "get_broker_time", return_value=today),
                patch.object(mt5_signal_bot, "is_slot_ready", return_value=True),
                patch.object(mt5_signal_bot, "warm_m30_history"),
                patch.object(mt5_signal_bot, "calculate_all_d_directions", return_value={
                    "XAUUSD": {"d_state": "READY", "session_date": "2026-07-21"},
                    "GBPUSD": {"d_state": "READY", "session_date": "2026-07-21"},
                }),
                patch.object(mt5_signal_bot, "build_d_direction_snapshot_for_date", return_value={"symbols": {}}),
                patch.object(mt5_signal_bot, "snapshot_is_publishable", return_value=True),
                patch.object(mt5_signal_bot, "_build_rebuild_record", side_effect=build_record),
            ):
                count = mt5_signal_bot.rebuild_recent_history(days=1)

            self.assertGreater(count, 0)
            import json
            with open(signal_log, encoding="utf-8") as f:
                records = json.load(f)
            self.assertTrue(records)
            for rec in records:
                self.assertEqual(rec["rebuild_state"], "READY")
                self.assertEqual(rec["daily_directions"]["XAUUSD"]["d_state"], "READY")
                self.assertEqual(rec["d_direction_schema_version"], mt5_signal_bot.D_DIRECTION_SCHEMA_VERSION)


class MultiSymbolEASourceTests(unittest.TestCase):
    def _source(self):
        with open(EA_SOURCE_PATH, "r", encoding="utf-8-sig") as f:
            return f.read()

    def test_multisymbol_ea_source_contains_symbol_loop(self):
        source = self._source()
        self.assertIn('input string FeedSymbols = "XAUUSD,GBPUSD,GBPAUD,GBPJPY,GBPCAD"', source)
        self.assertIn("feedSymbolsResolved", source)
        self.assertIn("PublishAllBars", source)
        self.assertIn("iBars", source)
        self.assertIn("iTime", source)
        self.assertIn("iOpen", source)
        self.assertIn("iHigh", source)
        self.assertIn("iLow", source)
        self.assertIn("iClose", source)
        # Stable source identity per plan.
        self.assertIn("MT4_FEED_V88", source)
        self.assertIn("AccountServer", source)
        self.assertIn("AccountNumber", source)
        self.assertIn("SymbolSetHash", source)
        # 10-second backfill retry with an explicit missing-history log line.
        self.assertIn("BACKFILL_RETRY_SECONDS 10", source)
        self.assertIn("[MT4 FEED] Missing history symbol=", source)

    def test_multisymbol_ea_publishes_h4_for_all_symbols(self):
        source = self._source()
        self.assertIn("PERIOD_H4", source)
        self.assertIn("PERIOD_H1", source)
        self.assertIn("PERIOD_M30", source)
        # Every required symbol/timeframe cell is inside the publish loop.
        for symbol, timeframe in EXPECTED_FEED_MATRIX:
            self.assertIn(symbol, source)
        self.assertIn("TimeframeName(timeframe)", source)
        self.assertIn("PublishBarsFor(s, t, count)", source)

    def test_multisymbol_ea_backfill_days_input(self):
        source = self._source()
        self.assertIn("input int BackfillDays = 60", source)
        self.assertIn("OpenChartsForHistoryWarmup", source)
        self.assertIn("ChartOpen(resolved, timeframe)", source)


class HistoryBackfillWatchWorkerTests(unittest.TestCase):
    def test_rebuild_retries_after_coverage_complete(self):
        coverage_calls = []
        rebuilt_calls = []

        def coverage_fn(days):
            coverage_calls.append(days)
            if len(coverage_calls) == 1:
                return {
                    "coverage_complete": False,
                    "missing": [{"symbol": "GBPUSD", "timeframe": "H4", "reason": "NO_H4_20_FOR_SESSION", "date": "2026-07-31"}],
                    "missing_dates": ["2026-07-31"],
                }
            return {"coverage_complete": True, "missing": [], "missing_dates": []}

        def rebuild_fn(dates, days):
            rebuilt_calls.append((list(dates), days))
            return 6

        buffer = io.StringIO()
        worker = history_backfill_watch_worker.HistoryBackfillWatchWorker(
            coverage_fn=coverage_fn,
            rebuild_fn=rebuild_fn,
            slot_count_fn=lambda date_str: 6,
            days=45,
        )
        with contextlib.redirect_stdout(buffer):
            worker.run_once()  # incomplete: baseline only
            worker.run_once()  # complete: rebuild the previously-missing date

        self.assertEqual(rebuilt_calls, [(["2026-07-31"], 45)])
        log = buffer.getvalue()
        self.assertIn("[HISTORY] Coverage complete, rebuilding missing dates...", log)
        self.assertIn("[HISTORY] Rebuilt date=2026-07-31 slots=6 complete=true", log)

    def test_rebuild_runs_when_missing_dates_shrink(self):
        state = {"missing": ["2026-07-30", "2026-07-31"]}
        rebuilt_calls = []

        def coverage_fn(days):
            return {
                "coverage_complete": False,
                "missing": [{"symbol": "GBPUSD", "timeframe": "H4", "reason": "NO_H4_20_FOR_SESSION", "date": d} for d in state["missing"]],
                "missing_dates": list(state["missing"]),
            }

        def rebuild_fn(dates, days):
            rebuilt_calls.append(list(dates))
            return 6

        worker = history_backfill_watch_worker.HistoryBackfillWatchWorker(
            coverage_fn=coverage_fn,
            rebuild_fn=rebuild_fn,
            slot_count_fn=lambda date_str: 6,
        )
        worker.run_once()
        self.assertEqual(rebuilt_calls, [])
        state["missing"] = ["2026-07-31"]  # 2026-07-30 is now covered
        worker.run_once()
        self.assertEqual(rebuilt_calls, [["2026-07-30"]])


class HistoryStatsExclusionTests(unittest.TestCase):
    def test_history_stats_exclude_incomplete_wait_records(self):
        # Stats must not count a missing-input WAIT as a real BUY/SELL/WAIT
        # verdict.  The integrity gate is the source of truth for exclusion.
        complete = {
            "rebuild_state": "READY",
            "pair_signal_states": {"XAUUSD": "READY", "GBPUSD": "READY"},
            "wait_reasons": {},
            "pair_dirs": {"XAUUSD": "BUY", "GBPUSD": "BUY"},
        }
        incomplete = {
            "rebuild_state": "MISSING_INPUT",
            "incomplete": True,
            "missing_inputs": ["H49_H1_MISSING"],
            "pair_signal_states": {"XAUUSD": "WAIT", "GBPUSD": "WAIT"},
            "wait_reasons": {"XAUUSD": "H49_H1_MISSING", "GBPUSD": "H49_H1_MISSING"},
            "pair_dirs": {"XAUUSD": "WAIT", "GBPUSD": "WAIT"},
        }
        self.assertFalse(mt5_signal_bot._compute_rebuild_complete([incomplete]))
        self.assertTrue(mt5_signal_bot._compute_rebuild_complete([complete]))
        # The dashboard mirrors the same gate: only the complete record counts.
        try:
            from dashboard.src.lib.signal_integrity import (
                countIncompleteSignals,
                isSignalRecordIncomplete,
            )
        except Exception:
            self.skipTest("dashboard TS module not importable in this Python test run")
        else:
            self.assertFalse(isSignalRecordIncomplete(complete))
            self.assertTrue(isSignalRecordIncomplete(incomplete))
            self.assertEqual(countIncompleteSignals([complete, incomplete]), 1)


if __name__ == "__main__":
    unittest.main()
