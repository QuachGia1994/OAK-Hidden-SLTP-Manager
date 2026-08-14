# -*- coding: utf-8 -*-
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from repositories.trade_audit_store import TradeAuditStore
from services.audit_dashboard_publisher import AuditDashboardPublisher
from services.public_freshness import STATUS_LIVE, SOURCE_MT5_LIVE


class TestPublisherLiveObservation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = TradeAuditStore(db_path=str(Path(self.tmp.name) / "a.db"))
        self.uid = "7398029@ICMarketsSC-MT5-6"
        self.store.upsert_account(
            account_uid=self.uid,
            profile_name="ICMarkets",
            broker="ICMarkets",
            currency="USD",
            public_alias="ICMarkets",
        )

    def tearDown(self):
        try:
            self.store.close()
        except Exception:
            pass
        self.tmp.cleanup()

    def test_live_observation_marks_mt5_source(self):
        pub = AuditDashboardPublisher(self.store, secret="s")
        # Use wall-clock now so freshness threshold remains LIVE under any run time.
        now = datetime.now(timezone.utc)
        live = pub.build_live(
            self.uid,
            account_info={
                "balance": 1000.0,
                "equity": 1005.5,
                "open_profit": 5.5,
            },
            positions=[{
                "symbol": "XAUUSD",
                "type": 0,
                "volume": 0.1,
                "price_open": 2400.0,
                "price_current": 2405.0,
                "profit": 5.5,
                "ticket": 99,
            }],
            observed_at_utc=now,
        )
        self.assertEqual(live["source"], SOURCE_MT5_LIVE)
        self.assertEqual(live["source_status"], STATUS_LIVE)
        self.assertEqual(live["positions_count"], 1)
        self.assertEqual(live["open_positions"][0]["symbol"], "XAUUSD")
        self.assertTrue(live["open_positions"][0]["floating_available"])
        self.assertAlmostEqual(live["floating_profit"], 5.5)

    def test_missing_profit_not_zero(self):
        pub = AuditDashboardPublisher(self.store, secret="s")
        live = pub.build_live(
            self.uid,
            account_info={"balance": 1.0, "equity": 1.0},
            positions=[{
                "symbol": "GBPUSD+",
                "direction": "BUY",
                "volume": 0.2,
                "open_price": 1.2,
                "ticket": 1,
            }],
            observed_at_utc=datetime.now(timezone.utc),
        )
        row = live["open_positions"][0]
        self.assertIs(row["floating_available"], False)
        self.assertIsNone(row["floating_profit"])

    def test_push_live_failure_does_not_raise(self):
        pub = AuditDashboardPublisher(
            self.store, secret="s",
            dashboard_url="https://example.invalid", api_key="k",
        )
        with patch(
            "services.audit_dashboard_publisher.urllib.request.urlopen",
            side_effect=OSError("down"),
        ):
            out = pub.push_live(
                self.uid,
                account_info={"balance": 1.0, "equity": 1.0, "open_profit": 0.1},
                positions=[],
                observed_at_utc=datetime.now(timezone.utc),
            )
        self.assertFalse(out["pushed"])
        self.assertIn("live", out["results"])


if __name__ == "__main__":
    unittest.main()
