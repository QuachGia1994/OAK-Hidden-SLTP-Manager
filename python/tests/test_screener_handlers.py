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


def _make_tmpdir(prefix="oak-screener-"):
    """Create a temp dir; return (path, cleanup_func)."""
    tmpdir = tempfile.mkdtemp(prefix=prefix)

    def _cleanup():
        gc.collect()  # release any lingering SQLite file handles
        shutil.rmtree(tmpdir, ignore_errors=True)

    return tmpdir, _cleanup


class TestUpdateEodFrozenSubcommand(unittest.TestCase):
    """Regression: frozen oak-core must invoke ``eod_collector`` as a subcommand,
    NOT as ``-m eod_collector`` (which causes 'invalid choice')."""

    @mock.patch("oak_core.supervisor.accounts.subprocess.run")
    def test_frozen_uses_eod_collector_subcommand(self, mock_run):
        fake_proc = mock.Mock(returncode=0, stdout="", stderr="")
        mock_run.return_value = fake_proc

        with mock.patch.dict(os.environ, {"OAK_DATA_DIR": "C:\\fake"}):
            # Frozen mode
            with mock.patch.object(sys, "frozen", True, create=True):
                queries = AccountQueries()
                result = queries.update_eod()
                self.assertTrue(result["ok"])
                cmd = mock_run.call_args[1].get("cmd") or mock_run.call_args[0][0]
                self.assertEqual(cmd[0], sys.executable)
                self.assertEqual(cmd[1], "eod_collector")
                self.assertEqual(cmd[2], "update")
                cwd = mock_run.call_args[1].get("cwd", "")
                self.assertTrue(cwd.endswith("fake") or cwd == "C:\\fake")

            mock_run.reset_mock()

            # Dev mode
            with mock.patch.object(sys, "frozen", False, create=True):
                queries = AccountQueries()
                result = queries.update_eod()
                self.assertTrue(result["ok"])
                cmd = mock_run.call_args[1].get("cmd") or mock_run.call_args[0][0]
                self.assertEqual(cmd[:4],
                                 [sys.executable, "-m", "oak_core", "eod_collector"])

    @mock.patch("oak_core.supervisor.accounts.subprocess.run")
    def test_update_eod_with_date(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.dict(os.environ, {"OAK_DATA_DIR": "C:\\fake"}):
            with mock.patch.object(sys, "frozen", True, create=True):
                queries = AccountQueries()
                result = queries.update_eod(target_date="2026-08-01")
                cmd = mock_run.call_args[1].get("cmd") or mock_run.call_args[0][0]
                self.assertIn("--date", cmd)
                self.assertIn("2026-08-01", cmd)


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
