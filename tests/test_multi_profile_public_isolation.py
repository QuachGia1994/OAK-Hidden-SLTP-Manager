# -*- coding: utf-8 -*-
"""Publisher multi-profile isolation: distinct public ids and payloads."""
import tempfile
import unittest
from pathlib import Path

from repositories.trade_audit_store import TradeAuditStore
from services.audit_dashboard_publisher import AuditDashboardPublisher, public_account_id


class TestMultiProfilePublicIsolation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = TradeAuditStore(db_path=str(Path(self.tmp.name) / "audit.db"))
        self.secret = "isolation-secret"
        self.uids = {
            "Vantage": "Vantage-Live",
            "ICMarkets": "ICMarkets-Live",
            "VantageDemo": "Vantage-Demo",
        }
        for alias, uid in self.uids.items():
            self.store.upsert_account(
                account_uid=uid,
                profile_name=alias,
                broker=alias,
                currency="USD",
                public_alias=alias,
            )

    def tearDown(self):
        try:
            self.store.close()
        except Exception:
            pass
        self.tmp.cleanup()

    def test_public_ids_distinct_and_payloads_isolated(self):
        pub = AuditDashboardPublisher(self.store, secret=self.secret)
        ids = {}
        nets = {}
        for alias, uid in self.uids.items():
            acct_id = self.store.get_account_by_uid(uid)["id"]
            # Distinct closed P&L per account
            profit = {"Vantage": 100.0, "ICMarkets": -50.0, "VantageDemo": 10.0}[alias]
            self.store.upsert_deal(acct_id, {
                "deal_ticket": f"t-{alias}",
                "position_id": f"p-{alias}",
                "symbol": f"EURUSD.{alias[0]}",
                "deal_type": "SELL",
                "entry_type": "OUT",
                "volume": 0.1,
                "price": 1.1,
                "profit": profit,
                "commission": 0,
                "swap": 0,
                "fee": 0,
                "deal_time_utc": "2026-08-01T10:00:00+00:00",
            })
            payload = pub.build_all(uid)
            pid = payload["public_account_id"]
            self.assertEqual(pid, public_account_id(uid, self.secret))
            self.assertNotEqual(pid, uid)
            ids[alias] = pid
            nets[alias] = payload["performance"].get("net_profit")

        self.assertEqual(len(set(ids.values())), 3)
        self.assertNotEqual(nets["Vantage"], nets["ICMarkets"])
        self.assertNotEqual(nets["Vantage"], nets["VantageDemo"])
        self.assertNotEqual(nets["ICMarkets"], nets["VantageDemo"])


if __name__ == "__main__":
    unittest.main()
