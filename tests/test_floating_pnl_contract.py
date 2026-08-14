# -*- coding: utf-8 -*-
"""Floating P&L: never invent 0 when mark unavailable."""
import tempfile
import unittest
from pathlib import Path

from repositories.trade_audit_store import TradeAuditStore
from services.audit_dashboard_publisher import AuditDashboardPublisher


class TestFloatingPnlContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "audit.db"
        self.store = TradeAuditStore(db_path=str(self.db))
        self.uid = "VantageDemo"
        self.acct_id = self.store.upsert_account(
            account_uid=self.uid,
            profile_name="VantageDemo",
            broker="Vantage",
            currency="USD",
            public_alias="VantageDemo",
        )

    def tearDown(self):
        try:
            self.store.close()
        except Exception:
            pass
        self.tmp.cleanup()

    def test_unavailable_mark_is_explicit_not_zero(self):
        self.store.upsert_position(self.acct_id, {
            "position_id": "p1",
            "symbol": "GBPUSD+",
            "direction": "BUY",
            "open_price": 1.25,
            "initial_volume": 0.2,
            "open_time_utc": "2026-08-10T12:00:00+00:00",
            "source_type": "LIVE",
        })
        pub = AuditDashboardPublisher(self.store, secret="s3cret")
        positions = pub.build_positions(self.uid)
        self.assertEqual(len(positions), 1)
        row = positions[0]
        self.assertEqual(row["symbol"], "GBPUSD+")
        self.assertIs(row["floating_available"], False)
        self.assertIsNone(row["floating_profit"])
        self.assertIsNone(row["current_price"])
        self.assertNotEqual(row["floating_profit"], 0)

    def test_checkpoint_mark_surfaces_when_present(self):
        self.store.upsert_position(self.acct_id, {
            "position_id": "p2",
            "symbol": "XAUUSD.v",
            "direction": "SELL",
            "open_price": 2400.0,
            "initial_volume": 0.1,
            "open_time_utc": "2026-08-11T12:00:00+00:00",
            "source_type": "LIVE",
        })
        run_id = self.store.upsert_checkpoint_run(
            self.acct_id, "2026-08-11", 12,
            status="COMPLETED",
            captured_at_utc="2026-08-11T12:30:00+00:00",
        )
        self.store.upsert_checkpoint_position_state(run_id, {
            "position_id": "p2",
            "status_at_checkpoint": "STILL_OPEN",
            "volume": 0.1,
            "current_price": 2395.5,
            "floating_profit": 45.0,
        })
        pub = AuditDashboardPublisher(self.store, secret="s3cret")
        positions = pub.build_positions(self.uid)
        row = next(p for p in positions if p["symbol"] == "XAUUSD.v")
        self.assertIs(row["floating_available"], True)
        self.assertAlmostEqual(row["floating_profit"], 45.0)
        self.assertAlmostEqual(row["current_price"], 2395.5)


if __name__ == "__main__":
    unittest.main()
