# -*- coding: utf-8 -*-
"""Tests for the append-only trade audit store (data/trade_audit.db)."""
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_workspace_root = Path(__file__).resolve().parents[1]
if str(_workspace_root) not in sys.path:
    sys.path.insert(0, str(_workspace_root))

from repositories.trade_audit_store import (
    TradeAuditStore,
    position_identity,
    is_same_position,
)


class TradeAuditStoreTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="robot-sltp-trade-audit-")
        self.db_path = os.path.join(self._tmpdir.name, "trade_audit.db")
        self.store = TradeAuditStore(db_path=self.db_path, read_only=True)

    def tearDown(self):
        if self.store:
            self.store.close()
        self._tmpdir.cleanup()


class TestTradeAuditStoreBasics(TradeAuditStoreTestCase):
    def test_trade_ledger_is_append_only(self):
        account_id = self.store.upsert_account(
            account_uid="123@Vantage", profile_name="VantageDemo",
            broker="Vantage", server="Vantage-Server", currency="USD",
        )
        self.store.upsert_position(account_id, {
            "position_id": "111",
            "position_ticket": "111",
            "symbol": "XAUUSD",
            "direction": "SELL",
        })
        # Production mode blocks DELETE on ledger tables.
        with self.assertRaises(PermissionError):
            self.store._guarded_execute("DELETE FROM positions WHERE account_id=?", (account_id,))
        with self.assertRaises(PermissionError):
            self.store._guarded_execute("DELETE FROM deals WHERE account_id=?", (account_id,))
        with self.assertRaises(PermissionError):
            self.store._guarded_execute("DELETE FROM equity_samples WHERE account_id=?", (account_id,))
        with self.assertRaises(PermissionError):
            self.store._guarded_execute("DELETE FROM audit_events WHERE account_id=?", (account_id,))
        # Position still there.
        self.assertIsNotNone(self.store.get_position(account_id, "111"))

    def test_trade_ledger_delete_allowed_when_read_only_off(self):
        self.store.close()
        self.store = TradeAuditStore(db_path=self.db_path, read_only=False)
        account_id = self.store.upsert_account(account_uid="1@S", broker="S", server="S")
        self.store.upsert_position(account_id, {"position_id": "1", "symbol": "EURUSD"})
        self.store._guarded_execute("DELETE FROM positions WHERE account_id=?", (account_id,))
        self.assertIsNone(self.store.get_position(account_id, "1"))

    def test_schema_tables_created_and_migrations_recorded(self):
        tables = {
            row[0] for row in self.store._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for required in (
            "accounts", "checkpoint_runs", "account_snapshots", "positions", "deals",
            "checkpoint_position_states", "equity_samples", "cash_flows", "audit_events",
            "app_settings", "schema_version",
        ):
            self.assertIn(required, tables)
        self.assertGreaterEqual(self.store.schema_version, 2)

    def test_investor_tables_exist(self):
        tables = {
            row[0] for row in self.store._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        for required in (
            "investors", "investment_accounts", "capital_contributions", "withdrawals",
            "unit_balances", "high_water_marks", "performance_fee_events",
        ):
            self.assertIn(required, tables)

    def test_wal_enabled_and_foreign_keys(self):
        mode = self.store._conn.execute("PRAGMA journal_mode").fetchone()[0]
        self.assertEqual(mode.upper(), "WAL")
        fk = self.store._conn.execute("PRAGMA foreign_keys").fetchone()[0]
        self.assertEqual(fk, 1)

    def test_account_upsert_is_idempotent(self):
        first = self.store.upsert_account("42@S", profile_name="A", broker="B", server="S")
        second = self.store.upsert_account("42@S", profile_name="A", broker="B", server="S")
        self.assertEqual(first, second)
        self.assertEqual(len(self.store.list_accounts()), 1)

    def test_position_identity_helpers(self):
        a = {"account_uid": "1@S", "position_id": "100"}
        b = {"account_uid": "1@S", "position_id": "101"}
        self.assertTrue(is_same_position(a, a))
        self.assertFalse(is_same_position(a, b))
        self.assertFalse(is_same_position(
            {"account_uid": "1@S", "position_id": "100"},
            {"account_uid": "2@S", "position_id": "100"},
        ))
        self.assertEqual(position_identity("1@S", "100"), "1@S::100")

    def test_checkpoint_run_idempotency(self):
        account_id = self.store.upsert_account("9@S", broker="S", server="S")
        first = self.store.upsert_checkpoint_run(
            account_id, broker_date="2026-08-04", checkpoint_hour=3,
            interval_start="2026-08-03T16:00:00+00:00",
            interval_end="2026-08-04T03:00:00+00:00",
            status="COMPLETED",
        )
        second = self.store.upsert_checkpoint_run(
            account_id, broker_date="2026-08-04", checkpoint_hour=3,
            interval_start="2026-08-03T16:00:00+00:00",
            interval_end="2026-08-04T03:00:00+00:00",
            status="COMPLETED",
        )
        self.assertEqual(first, second)
        self.assertEqual(len(self.store.list_checkpoint_runs(account_id)), 1)


class TestAuditChain(TradeAuditStoreTestCase):
    def test_audit_chain_integrity(self):
        account_id = self.store.upsert_account("5@S", broker="S", server="S")
        h1 = self.store.append_audit_event(account_id, "POSITION_OPEN", "position", "1", {"symbol": "XAUUSD"})
        h2 = self.store.append_audit_event(account_id, "POSITION_CLOSE", "position", "1", {"symbol": "XAUUSD", "pnl": -10.5})
        h3 = self.store.append_audit_event(account_id, "CHECKPOINT", "checkpoint", "2026-08-04:3", {"status": "OK"})
        self.assertTrue(all(h1 and h2 and h3))
        result = self.store.verify_audit_chain(account_id)
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["events"], 3)
        self.assertEqual(len(h3), 64)  # SHA-256 hex digest
        # Tamper with an event payload: chain must break.
        self.store._conn.execute(
            "UPDATE audit_events SET payload_json=? WHERE entity_id=?",
            ('{"symbol": "XAUUSD", "pnl": 999}', "1"),
        )
        self.store._conn.commit()
        broken = self.store.verify_audit_chain(account_id)
        self.assertFalse(broken["ok"])
        self.assertIsNotNone(broken["first_broken"])

    def test_audit_chain_empty_account_ok(self):
        account_id = self.store.upsert_account("6@S", broker="S", server="S")
        result = self.store.verify_audit_chain(account_id)
        self.assertTrue(result["ok"])
        self.assertEqual(result["events"], 0)


if __name__ == "__main__":
    unittest.main()
