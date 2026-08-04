# -*- coding: utf-8 -*-
"""Tests for screener handlers — EOD update, D1 scan filter, and data-root routing.

Covers the frozen-binary ``invalid choice: 'eod_collector'`` regression and the
real D1 scanner integration via AccountQueries.run_filter().
"""
import gc
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_python_root = Path(__file__).resolve().parents[1]
if str(_python_root) not in sys.path:
    sys.path.insert(0, str(_python_root))

_repo_root = _python_root.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from oak_core.supervisor.accounts import AccountQueries  # noqa: E402
from oak_core.supervisor.accounts import _build_eod_cmd, _parse_eod_progress  # noqa: E402


def _make_tmpdir(prefix="oak-screener-"):
    """Create a temp dir; return (path, cleanup_func)."""
    tmpdir = tempfile.mkdtemp(prefix=prefix)

    def _cleanup():
        gc.collect()  # release any lingering SQLite file handles
        shutil.rmtree(tmpdir, ignore_errors=True)

    return tmpdir, _cleanup


class TestBuildEodCmd(unittest.TestCase):
    """_build_eod_cmd produces correct command for frozen vs dev mode."""

    def test_build_cmd_frozen(self):
        with mock.patch.dict(os.environ, {"OAK_DATA_DIR": "C:\\fake"}):
            with mock.patch.object(sys, "frozen", True, create=True):
                cmd = _build_eod_cmd()
                self.assertEqual(cmd[0], sys.executable)
                self.assertEqual(cmd[1], "eod_collector")
                self.assertEqual(cmd[2], "update")

    def test_build_cmd_dev(self):
        with mock.patch.dict(os.environ, {"OAK_DATA_DIR": "C:\\fake"}):
            with mock.patch.object(sys, "frozen", False, create=True):
                cmd = _build_eod_cmd()
                self.assertEqual(cmd[:4],
                                 [sys.executable, "-m", "oak_core", "eod_collector"])

    def test_build_cmd_with_date(self):
        with mock.patch.dict(os.environ, {"OAK_DATA_DIR": "C:\\fake"}):
            with mock.patch.object(sys, "frozen", True, create=True):
                cmd = _build_eod_cmd(target_date="2026-08-01")
                self.assertEqual(cmd[-2:], ["--date", "2026-08-01"])


class TestParseEodProgress(unittest.TestCase):
    """_parse_eod_progress parses collector stdout lines into progress dicts."""

    def test_progress_line(self):
        result = _parse_eod_progress("[VPS EOD] 10/637 (5%)")
        self.assertEqual(result["percent"], 5)
        self.assertEqual(result["current"], 10)
        self.assertEqual(result["total"], 637)

    def test_fetching_line(self):
        result = _parse_eod_progress("[VPS EOD] Fetching 637 symbols for 2026-08-04...")
        self.assertEqual(result["percent"], 1)
        self.assertEqual(result["total"], 637)
        self.assertEqual(result["current"], 0)

    def test_saved_line(self):
        result = _parse_eod_progress(
            "[2026-08-04 16:00:00] [INFO] [eod_collector] [VPS UPDATE] Saved 637 records for 2026-08-04"
        )
        self.assertEqual(result["percent"], 100)

    def test_random_line_returns_none(self):
        result = _parse_eod_progress("random noise, no progress here")
        self.assertIsNone(result)


class TestUpdateEodStreamsEvents(unittest.TestCase):
    """update_eod spawns a background thread, streams progress events, and returns immediately."""

    def test_update_eod_returns_started_and_streams_events(self):
        import time

        # Fake Popen that yields progress lines then exits
        class FakePopen:
            def __init__(self, *args, **kwargs):
                self.stdout = iter([
                    "[VPS EOD] Fetching 2 symbols for 2026-08-04...",
                    "[VPS EOD] 1/2 (50%)",
                    "[VPS EOD] 2/2 (100%)",
                ])
                self.returncode = 0

            def wait(self, timeout=None):
                return 0

            def kill(self):
                pass

        events: list = []
        with mock.patch("oak_core.supervisor.accounts.subprocess.Popen", FakePopen):
            with mock.patch.dict(os.environ, {"OAK_DATA_DIR": "C:\\fake"}):
                queries = AccountQueries(emit_event=lambda name, data: events.append((name, data)))
                res = queries.update_eod(target_date="2026-08-04")
                self.assertEqual(res, {"started": True})

                # Wait for the background thread to finish (up to 2s)
                deadline = time.time() + 2
                while time.time() < deadline:
                    if any(e[0] == "eod.done" for e in events):
                        break
                    time.sleep(0.05)

                # Verify we got progress events with percent 50
                progress_events = [e for e in events if e[0] == "eod.progress"]
                self.assertTrue(len(progress_events) > 0, "no eod.progress events emitted")
                percents = [e[1]["percent"] for e in progress_events]
                self.assertIn(50, percents)

                # Verify we got an eod.done with ok=True
                done_events = [e for e in events if e[0] == "eod.done"]
                self.assertEqual(len(done_events), 1, "expected exactly one eod.done")
                self.assertTrue(done_events[0][1]["ok"])
                self.assertEqual(done_events[0][1]["returncode"], 0)


class TestRunFilterReadsTempMarketDb(unittest.TestCase):
    """run_filter reads a temp market.db and returns real D1 scan results."""

    def _seed_db(self, tmpdir: str) -> None:
        """Create data/market.db with 3 symbols × 3 bars each."""
        db_dir = Path(tmpdir) / "data"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "market.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS eod_prices (
                date TEXT NOT NULL, symbol TEXT NOT NULL, exchange TEXT NOT NULL,
                open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL,
                close REAL NOT NULL, reference_price REAL, ceiling_price REAL,
                floor_price REAL, volume REAL NOT NULL DEFAULT 0,
                value REAL NOT NULL DEFAULT 0, source TEXT NOT NULL DEFAULT 'unknown',
                collected_at TEXT NOT NULL, foreign_buy_volume REAL,
                foreign_sell_volume REAL, foreign_buy_value REAL,
                foreign_sell_value REAL, adjusted_close REAL,
                PRIMARY KEY (date, symbol)
            )
        """)
        symbols = [
            # AAA: clear uptrend  → BUY
            ("AAA", "HOSE", [(10, 10.5, 9.5, 10.2), (10.2, 11.0, 10.0, 10.8),
                             (10.8, 11.5, 10.5, 11.3)]),
            # BBB: clear downtrend → SELL
            ("BBB", "HOSE", [(20, 20.5, 19.5, 20.2), (20.2, 19.0, 18.5, 18.8),
                             (18.8, 17.5, 17.0, 17.2)]),
            # CCC: flat → WAIT
            ("CCC", "HNX", [(15, 15.5, 14.5, 15.0), (15.0, 15.5, 14.8, 15.1),
                            (15.1, 15.5, 14.9, 15.0)]),
        ]
        dates = ["2026-07-29", "2026-07-30", "2026-07-31"]
        for sym, exch, bars in symbols:
            for d, (o, h, l, c) in zip(dates, bars):
                conn.execute(
                    "INSERT INTO eod_prices "
                    "(date, symbol, exchange, open, high, low, close, volume, "
                    " value, source, collected_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 10000, 100000, 'test', '2026-08-01T00:00:00')",
                    (d, sym, exch, o, h, l, c),
                )
        conn.commit()
        conn.close()

    def test_run_filter_returns_ready_with_recommendations(self):
        tmpdir, cleanup = _make_tmpdir()
        try:
            self._seed_db(tmpdir)
            with mock.patch.dict(os.environ, {"OAK_DATA_DIR": tmpdir}):
                queries = AccountQueries()
                result = queries.run_filter(limit=10)
                self.assertTrue(result["ok"])
                self.assertEqual(result["status"], "READY")
                self.assertGreaterEqual(result["scanned"], 3)
                self.assertGreaterEqual(result["buy"] + result["sell"], 2)
                self.assertTrue(len(result["recommendations"]) > 0)
                directions = {r["symbol"]: r["direction"]
                              for r in result["recommendations"]}
                self.assertIn("AAA", directions)
                self.assertIn("BBB", directions)
                self.assertEqual(directions["AAA"], "BUY")
                self.assertEqual(directions["BBB"], "SELL")
        finally:
            cleanup()

    def test_run_filter_limit(self):
        tmpdir, cleanup = _make_tmpdir()
        try:
            self._seed_db(tmpdir)
            with mock.patch.dict(os.environ, {"OAK_DATA_DIR": tmpdir}):
                queries = AccountQueries()
                result = queries.run_filter(limit=1)
                self.assertTrue(result["ok"])
                self.assertLessEqual(len(result["recommendations"]), 1)
        finally:
            cleanup()


    def test_run_filter_does_not_mutate_db(self):
        """Regression: run_filter must NOT write to market.db (read-only contract)."""
        tmpdir, cleanup = _make_tmpdir(prefix="oak-screener-ro-")
        try:
            self._seed_db(tmpdir)
            db_path = Path(tmpdir) / "data" / "market.db"
            db_bytes_before = db_path.read_bytes()
            with mock.patch.dict(os.environ, {"OAK_DATA_DIR": tmpdir}):
                queries = AccountQueries()
                result = queries.run_filter(limit=10)
                self.assertTrue(result["ok"])
                self.assertEqual(result["status"], "READY")
                # The DB file must be byte-identical — no writes occurred.
                db_bytes_after = db_path.read_bytes()
                self.assertEqual(db_bytes_before, db_bytes_after,
                                 "run_filter mutated market.db — expected read-only")
        finally:
            cleanup()


class TestRunFilterNoData(unittest.TestCase):
    """run_filter returns NO_DATA when market.db does not exist."""

    def test_no_data_returns_ok_no_data(self):
        tmpdir, cleanup = _make_tmpdir(prefix="oak-screener-empty-")
        try:
            with mock.patch.dict(os.environ, {"OAK_DATA_DIR": tmpdir}):
                queries = AccountQueries()
                result = queries.run_filter()
                self.assertTrue(result["ok"])
                self.assertEqual(result["status"], "NO_DATA")
                self.assertEqual(result["scanned"], 0)
                self.assertEqual(result["recommendations"], [])
        finally:
            cleanup()


class TestScreenerListUsesDataRoot(unittest.TestCase):
    """screener_list must read from OAK_DATA_DIR, not hardcoded _REPO_ROOT."""

    def _seed_db(self, tmpdir: str) -> None:
        db_dir = Path(tmpdir) / "data"
        db_dir.mkdir(parents=True, exist_ok=True)
        db_path = db_dir / "market.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS eod_prices (
                date TEXT NOT NULL, symbol TEXT NOT NULL, exchange TEXT NOT NULL,
                open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL,
                close REAL NOT NULL, reference_price REAL, ceiling_price REAL,
                floor_price REAL, volume REAL NOT NULL DEFAULT 0,
                value REAL NOT NULL DEFAULT 0, source TEXT NOT NULL DEFAULT 'unknown',
                collected_at TEXT NOT NULL, foreign_buy_volume REAL,
                foreign_sell_volume REAL, foreign_buy_value REAL,
                foreign_sell_value REAL, adjusted_close REAL,
                PRIMARY KEY (date, symbol)
            )
        """)
        conn.execute(
            "INSERT INTO eod_prices "
            "(date, symbol, exchange, open, high, low, close, volume, "
            " value, source, collected_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 5000, 50000, 'test', '2026-08-01T00:00:00')",
            ("2026-08-01", "XYZ", "HOSE", 10.0, 10.5, 9.5, 10.2),
        )
        conn.commit()
        conn.close()

    def test_screener_list_reads_from_data_root(self):
        tmpdir, cleanup = _make_tmpdir(prefix="oak-screener-list-")
        try:
            self._seed_db(tmpdir)
            with mock.patch.dict(os.environ, {"OAK_DATA_DIR": tmpdir}):
                queries = AccountQueries()
                rows = queries.screener_list(limit=10)
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["symbol"], "XYZ")
                self.assertEqual(rows[0]["date"], "2026-08-01")
                self.assertAlmostEqual(rows[0]["close"], 10.2)
        finally:
            cleanup()

    def test_screener_list_empty_when_no_db(self):
        tmpdir, cleanup = _make_tmpdir(prefix="oak-screener-list-empty-")
        try:
            with mock.patch.dict(os.environ, {"OAK_DATA_DIR": tmpdir}):
                queries = AccountQueries()
                rows = queries.screener_list()
                self.assertEqual(rows, [])
        finally:
            cleanup()


if __name__ == "__main__":
    unittest.main()
