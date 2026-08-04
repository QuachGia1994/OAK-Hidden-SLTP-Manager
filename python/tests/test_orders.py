# -*- coding: utf-8 -*-
"""Tests for Phase 4/5 order management (Â§9) â€” scheduled trades, scheduled
closes, pending partials (mirrors Native Qt "Chá» xá»­ lĂ½" tab + Telegram cmds)."""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_python_root = Path(__file__).resolve().parents[1]
if str(_python_root) not in sys.path:
    sys.path.insert(0, str(_python_root))
_repo_root = _python_root.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from repositories.sqlite_store import SQLiteStore  # noqa: E402
from oak_core.supervisor import orders as orders_module  # noqa: E402
from oak_core.supervisor import SupervisorApp  # noqa: E402
from oak_core.ipc.server import IpcServer  # noqa: E402


class OrdersTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="oak-orders-")
        self.db_path = os.path.join(self._tmpdir.name, "oak_state.db")
        self.store = SQLiteStore(self.db_path)

    def tearDown(self):
        try:
            self.store.close()
        except Exception:
            pass
        self._tmpdir.cleanup()

    def _patch_store(self):
        return patch("oak_core.supervisor.orders._store", return_value=self.store)


class TestScheduledTrades(OrdersTestCase):
    def test_add_and_list_scheduled_trade(self):
        self.store.add_scheduled_trade({
            "id": 1, "symbol": "XAUUSD", "type": 0, "lot": "0.10",
            "time": "09:30", "date": "2026-08-05", "sl": "500", "tp": "10000",
            "status": "waiting",
        })
        with self._patch_store():
            trades = orders_module.scheduled_trades_list()
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["symbol"], "XAUUSD")
        self.assertEqual(trades[0]["type"], 0)
        self.assertEqual(trades[0]["lot"], "0.10")

    def test_delete_scheduled_trade(self):
        self.store.add_scheduled_trade({
            "id": 2, "symbol": "EURUSD", "type": 1, "lot": "0.05",
            "time": "10:00", "date": "2026-08-05", "status": "waiting",
        })
        trade_id = self.store.get_scheduled_trades()[0]["id"]
        with self._patch_store():
            result = orders_module.delete_scheduled_trade(trade_id)
        self.assertTrue(result["deleted"])
        with self._patch_store():
            self.assertEqual(orders_module.scheduled_trades_list(), [])


class TestScheduledCloses(OrdersTestCase):
    def test_add_list_clear(self):
        self.store.add_scheduled_close({"time": "15:30", "date": "2026-08-05", "filter": "all", "sym": ""})
        with self._patch_store():
            closes = orders_module.scheduled_closes_list()
        self.assertEqual(len(closes), 1)
        self.assertEqual(closes[0]["filter"], "all")
        with self._patch_store():
            orders_module.clear_scheduled_closes()
        with self._patch_store():
            self.assertEqual(orders_module.scheduled_closes_list(), [])


class TestOrdersSummary(OrdersTestCase):
    def test_summary_sections(self):
        self.store.add_scheduled_trade({
            "id": 3, "symbol": "GBPUSD", "type": 0, "lot": "0.20",
            "time": "08:00", "date": "2026-08-05", "status": "waiting",
        })
        with self._patch_store():
            summary = orders_module.orders_summary()
        self.assertIn("scheduled_trades", summary)
        self.assertIn("scheduled_closes", summary)
        self.assertIn("pending_partials", summary)
        self.assertEqual(len(summary["scheduled_trades"]), 1)


class TestOrderHandlers(unittest.TestCase):
    def _make(self, text, db_path):
        stdin = io.StringIO(text)
        stdout = io.StringIO()
        stderr = io.StringIO()
        server = IpcServer(stdin=stdin, stdout=stdout, stderr=stderr)
        store = SQLiteStore(db_path)
        app = SupervisorApp(server=server)
        self._store_ref = store
        return server, stdout, app

    def _run(self, text, db_path):
        server, stdout, app = self._make(text, db_path)
        with patch("oak_core.supervisor.orders._store", return_value=self._store_ref):
            app.run()
        try:
            return [json.loads(l) for l in stdout.getvalue().splitlines() if l.strip()]
        finally:
            try:
                self._store_ref.close()
            except Exception:
                pass

    def test_orders_summary_handler(self):
        with tempfile.TemporaryDirectory(prefix="oak-ord-ipc-") as tmp:
            db = os.path.join(tmp, "oak_state.db")
            seed = SQLiteStore(db)
            seed.add_scheduled_trade({
                "id": 4, "symbol": "XAUUSD", "type": 1, "lot": "0.01",
                "time": "11:00", "date": "2026-08-05", "status": "waiting",
            })
            seed.close()
            responses = self._run(
                '{"v":1,"id":"o1","method":"orders.summary"}\n', db)
            self.assertTrue(responses[0]["ok"])
            self.assertEqual(len(responses[0]["result"]["scheduled_trades"]), 1)

    def test_add_scheduled_trade_missing_param_errors(self):
        with tempfile.TemporaryDirectory(prefix="oak-ord-ipc-") as tmp:
            db = os.path.join(tmp, "oak_state.db")
            responses = self._run(
                '{"v":1,"id":"o2","method":"orders.add_scheduled_trade","params":{"symbol":"XAUUSD"}}\n', db)
            self.assertFalse(responses[0]["ok"])


if __name__ == "__main__":
    unittest.main()


