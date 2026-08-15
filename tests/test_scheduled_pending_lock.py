# -*- coding: utf-8 -*-
"""Adversarial tests: scheduled pending append under lock (race / duplicate)."""
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from domain.copy_trade_manager import CopyTradeManager
from domain.json_io import load_json, save_json


class TestScheduledPendingLock(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "waiting_test.json")
        self.cm = object.__new__(CopyTradeManager)
        self.cm.config = {"profile_name": "VantageDemo"}
        self.cm.scheduled_file = self.path
        self.cm.scheduled_trades = []
        self.cm.notify = MagicMock()
        save_json(self.path, [])

    def tearDown(self):
        self.tmp.cleanup()

    def test_append_pending_unique_and_dup(self):
        created = {"trade": None, "dup": False}

        def _append(trades, symbol="GBPAUD+", t_type=1, lot="0.01", time_val="20:00:00", date="2026-07-09"):
            for t in trades:
                if (
                    t.get("status") in ("waiting", "executing")
                    and t.get("symbol") == symbol
                    and int(t.get("type", -1)) == int(t_type)
                ):
                    created["dup"] = True
                    return trades
            existing_ids = {t.get("id") for t in trades}
            new_id = 12345
            while new_id in existing_ids:
                new_id += 1
            nt = {
                "symbol": symbol,
                "type": int(t_type),
                "lot": lot,
                "sl": "0",
                "tp": "0",
                "time": time_val,
                "date": date,
                "status": "waiting",
                "id": new_id,
            }
            trades.append(nt)
            created["trade"] = nt
            created["dup"] = False
            return trades

        r1 = self.cm._with_scheduled_file_lock(lambda t: _append(t))
        self.assertIsNotNone(r1)
        self.assertEqual(len(r1), 1)
        self.assertFalse(created["dup"])

        r2 = self.cm._with_scheduled_file_lock(lambda t: _append(t))
        self.assertIsNotNone(r2)
        self.assertTrue(created["dup"])
        self.assertEqual(len(r2), 1)  # no second same-direction waiting

    def test_claim_prevents_double_execute(self):
        save_json(
            self.path,
            [{"id": 42, "status": "waiting", "symbol": "XAUUSD+", "type": 0, "lot": "0.01", "time": "10:00:00", "date": "2026-07-09"}],
        )
        self.cm.scheduled_trades = load_json(self.path, [])
        c1 = self.cm._claim_scheduled_trade(42)
        self.assertIsNotNone(c1)
        self.assertEqual(c1["status"], "executing")
        c2 = self.cm._claim_scheduled_trade(42)
        self.assertIsNone(c2)


if __name__ == "__main__":
    unittest.main()
