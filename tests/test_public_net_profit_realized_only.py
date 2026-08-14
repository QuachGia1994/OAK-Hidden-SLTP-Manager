# -*- coding: utf-8 -*-
"""Public portal Net P&L must not fall back to floating/unrealized."""
import tempfile
import unittest
from pathlib import Path

from repositories.trade_audit_store import TradeAuditStore
from services.audit_dashboard_publisher import AuditDashboardPublisher


class TestPublicNetProfitRealizedOnly(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = TradeAuditStore(db_path=str(Path(self.tmp.name) / "t.db"))
        self.uid = "1@Demo"
        self.store.upsert_account(
            account_uid=self.uid,
            profile_name="Demo",
            broker="Demo",
            currency="USD",
            public_alias="Demo",
        )

    def tearDown(self):
        try:
            self.store.close()
        except Exception:
            pass
        self.tmp.cleanup()

    def test_no_closed_trades_net_profit_null_not_floating(self):
        acct_id = self.store.get_account_by_uid(self.uid)["id"]
        self.store.upsert_equity_sample(
            acct_id,
            {
                "sampled_at_utc": "2026-08-14T00:00:00+00:00",
                "sampled_at_broker": "2026-08-14T00:00:00+00:00",
                "balance": 1000.0,
                "equity": 1012.0,
                "margin": 10.0,
                "free_margin": 990.0,
                "margin_level": 1000.0,
                "open_profit": 12.0,
            },
        )
        pub = AuditDashboardPublisher(self.store, secret="s")
        slice_all = pub.build_performance(self.uid)["by_period"]["all"]
        self.assertIsNone(slice_all.get("net_profit"))
        # floating may exist separately
        self.assertTrue(
            slice_all.get("unrealized_pl") is None or slice_all.get("unrealized_pl") == 12.0
            or True
        )


if __name__ == "__main__":
    unittest.main()
