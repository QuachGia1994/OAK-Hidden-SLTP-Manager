# -*- coding: utf-8 -*-
"""Tests for MT5DealReconciler — idempotency, restart survival, reason mapping."""
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

_workspace_root = Path(__file__).resolve().parents[1]
if str(_workspace_root) not in sys.path:
    sys.path.insert(0, str(_workspace_root))

from repositories.trade_audit_store import TradeAuditStore
from services.mt5_deal_reconciler import (
    MT5DealReconciler,
    classify_reason,
    DEAL_REASON_CLIENT,
    DEAL_REASON_SL,
    DEAL_REASON_TP,
)


# --------------------------------------------------------------------- #
# Fake MT5 module
# --------------------------------------------------------------------- #
# In-window unix epoch: 2026-08-04T10:00:00+00:00 (inside the default 7-day window).
DEAL_EPOCH = 1785837600


def make_deal(**overrides):
    defaults = {
        "ticket": 1000,
        "order": 900,
        "position_id": 500,
        "time": DEAL_EPOCH,           # unix epoch (UTC) inside test window
        "type": 0,                    # DEAL_TYPE_BUY
        "entry": 0,                   # DEAL_ENTRY_IN
        "reason": DEAL_REASON_CLIENT, # DEAL_REASON_CLIENT
        "volume": 0.10,
        "price": 2500.0,
        "profit": 0.0,
        "commission": -0.5,
        "swap": 0.0,
        "fee": 0.0,
        "symbol": "XAUUSD",
        "magic": 88000,
        "comment": "OAK88-abc",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class FakeMT5:
    def __init__(self, deals=None):
        self.deals = deals or []
        self.last_from = None
        self.last_to = None
        self.calls = 0

    def history_deals_get(self, from_dt, to_dt):
        self.calls += 1
        self.last_from = from_dt
        self.last_to = to_dt
        if self.deals is None:
            return None
        # Real MT5 filters by window: mimic it so the advanced cursor
        # naturally returns nothing on the second call.
        f_ts = from_dt.timestamp()
        t_ts = to_dt.timestamp()
        return [
            d for d in self.deals
            if d.time is not None and f_ts <= int(d.time) <= t_ts
        ]


def make_account_info(**overrides):
    info = {"login": 12345, "server": "Vantage-Server", "currency": "USD", "account_type": "demo"}
    info.update(overrides)
    return info


class ReconcilerTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="robot-sltp-reconciler-")
        self.db_path = os.path.join(self._tmpdir.name, "trade_audit.db")
        self.store = TradeAuditStore(db_path=self.db_path, read_only=True)

    def tearDown(self):
        if self.store:
            self.store.close()
        self._tmpdir.cleanup()

    def make_reconciler(self, fake_mt5):
        return MT5DealReconciler(self.store, fake_mt5)

    def account_uid(self):
        return "12345@Vantage-Server"


class TestDealReconciliation(ReconcilerTestCase):
    def test_duplicate_deal_is_idempotent(self):
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        deal = make_deal(ticket=777, reason=DEAL_REASON_SL, profit=-12.5,
                         entry=1, symbol="XAUUSD", position_id=500)
        fake = FakeMT5([deal])
        rec = self.make_reconciler(fake)

        first = rec.reconcile(self.account_uid(), make_account_info(), now_utc=now,
                              profile_name="VantageDemo", broker="Vantage", currency="USD")
        second = rec.reconcile(self.account_uid(), make_account_info(), now_utc=now + timedelta(hours=1),
                               profile_name="VantageDemo", broker="Vantage", currency="USD")
        # Second call must not duplicate the deal (cursor advanced past it).
        deals = self.store.list_deals(first["account_id"])
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0]["deal_ticket"], "777")
        self.assertEqual(second["deals_upserted"], 0)

    def test_deal_reconciliation_survives_restart(self):
        """Reconcile, reopen store on same db file, reconcile again -> no dupes."""
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        deal = make_deal(ticket=888, reason=DEAL_REASON_TP, profit=25.0,
                         entry=1, symbol="GBPUSD", position_id=600)
        fake = FakeMT5([deal])
        rec = self.make_reconciler(fake)
        first = rec.reconcile(self.account_uid(), make_account_info(), now_utc=now,
                              profile_name="VantageDemo", broker="Vantage", currency="USD")
        account_id = first["account_id"]

        # Simulate restart: fresh store + fresh reconciler on same file.
        self.store.close()
        self.store = TradeAuditStore(db_path=self.db_path, read_only=True)
        rec2 = self.make_reconciler(FakeMT5([]))
        second = rec2.reconcile(self.account_uid(), make_account_info(), now_utc=now + timedelta(hours=2),
                                profile_name="VantageDemo", broker="Vantage", currency="USD")
        self.assertEqual(second["account_id"], account_id)
        self.assertEqual(second["restart_recovery"], False)
        deals = self.store.list_deals(account_id)
        self.assertEqual(len(deals), 1)
        self.assertEqual(deals[0]["deal_ticket"], "888")

    def test_closed_and_reopened_same_symbol_are_distinct(self):
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        deal_a = make_deal(ticket=2001, position_id=901, symbol="XAUUSD", entry=1, reason=DEAL_REASON_SL, profit=-5)
        deal_b = make_deal(ticket=2002, position_id=902, symbol="XAUUSD", entry=1, reason=DEAL_REASON_TP, profit=9)
        fake = FakeMT5([deal_a, deal_b])
        rec = self.make_reconciler(fake)
        result = rec.reconcile(self.account_uid(), make_account_info(), now_utc=now,
                               profile_name="VantageDemo", broker="Vantage", currency="USD")
        deals = self.store.list_deals(result["account_id"])
        self.assertEqual(len(deals), 2)
        self.assertEqual({d["position_id"] for d in deals}, {"901", "902"})
        self.assertEqual({d["symbol"] for d in deals}, {"XAUUSD"})

    def test_hedging_two_positions_same_symbol_distinct(self):
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        open_a = make_deal(ticket=3001, position_id=701, symbol="EURUSD", entry=0, type=0, reason=DEAL_REASON_CLIENT)
        open_b = make_deal(ticket=3002, position_id=702, symbol="EURUSD", entry=0, type=1, reason=DEAL_REASON_CLIENT)
        fake = FakeMT5([open_a, open_b])
        rec = self.make_reconciler(fake)
        result = rec.reconcile(self.account_uid(), make_account_info(), now_utc=now,
                               profile_name="VantageDemo", broker="Vantage", currency="USD")
        deals = self.store.list_deals(result["account_id"])
        self.assertEqual(len(deals), 2)
        self.assertEqual({d["position_id"] for d in deals}, {"701", "702"})
        # Both are entry deals: no close reason category.
        self.assertTrue(all(d["reason_category"] == "" for d in deals))

    def test_partial_close_is_preserved(self):
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        # Partial close: same position_id, second deal smaller volume.
        deal_open = make_deal(ticket=4001, position_id=801, symbol="XAUUSD", entry=0, volume=0.50,
                              reason=DEAL_REASON_CLIENT, profit=0)
        deal_partial = make_deal(ticket=4002, position_id=801, symbol="XAUUSD", entry=1, volume=0.25,
                                 reason=DEAL_REASON_TP, profit=40.0)
        fake = FakeMT5([deal_open, deal_partial])
        rec = self.make_reconciler(fake)
        result = rec.reconcile(self.account_uid(), make_account_info(), now_utc=now,
                               profile_name="VantageDemo", broker="Vantage", currency="USD")
        deals = self.store.list_deals(result["account_id"], position_id="801")
        self.assertEqual(len(deals), 2)
        by_ticket = {d["deal_ticket"]: d for d in deals}
        self.assertEqual(by_ticket["4001"]["volume"], 0.50)
        self.assertEqual(by_ticket["4002"]["volume"], 0.25)
        self.assertEqual(by_ticket["4002"]["entry_type"], "OUT")

    def test_sl_reason_is_not_inferred_from_loss(self):
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        # Losing deal closed MANUALLY (CLIENT) — must NOT be categorized as SL.
        deal = make_deal(ticket=5001, position_id=601, symbol="XAUUSD", entry=1,
                         reason=DEAL_REASON_CLIENT, profit=-99.0)
        fake = FakeMT5([deal])
        rec = self.make_reconciler(fake)
        result = rec.reconcile(self.account_uid(), make_account_info(), now_utc=now,
                               profile_name="VantageDemo", broker="Vantage", currency="USD")
        deals = self.store.list_deals(result["account_id"])
        self.assertEqual(deals[0]["reason_category"], "CLOSED_MANUAL_DESKTOP")
        self.assertNotEqual(deals[0]["reason_category"], "CLOSED_SL")

    def test_tp_reason_is_not_inferred_from_profit(self):
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        # Winning deal stopped out (SO) — must NOT be categorized as TP.
        deal = make_deal(ticket=5002, position_id=602, symbol="XAUUSD", entry=1,
                         reason=3, profit=55.0)  # reason 3 = DEAL_REASON_SO
        fake = FakeMT5([deal])
        rec = self.make_reconciler(fake)
        result = rec.reconcile(self.account_uid(), make_account_info(), now_utc=now,
                               profile_name="VantageDemo", broker="Vantage", currency="USD")
        deals = self.store.list_deals(result["account_id"])
        self.assertEqual(deals[0]["reason_category"], "CLOSED_STOP_OUT")
        self.assertNotEqual(deals[0]["reason_category"], "CLOSED_TP")

    def test_entry_deal_has_no_close_reason(self):
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        deal = make_deal(ticket=6001, position_id=701, symbol="XAUUSD", entry=0,
                         reason=DEAL_REASON_CLIENT)
        fake = FakeMT5([deal])
        rec = self.make_reconciler(fake)
        result = rec.reconcile(self.account_uid(), make_account_info(), now_utc=now,
                               profile_name="VantageDemo", broker="Vantage", currency="USD")
        deals = self.store.list_deals(result["account_id"])
        self.assertEqual(deals[0]["reason_category"], "")

    def test_no_deals_from_history_is_graceful(self):
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        fake = FakeMT5(None)  # None return
        rec = self.make_reconciler(fake)
        result = rec.reconcile(self.account_uid(), make_account_info(), now_utc=now,
                               profile_name="VantageDemo", broker="Vantage", currency="USD")
        self.assertEqual(result["deals_upserted"], 0)
        self.assertIsNotNone(result["account_id"])

    def test_first_run_uses_default_window(self):
        now = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
        fake = FakeMT5([])
        rec = self.make_reconciler(fake)
        rec.reconcile(self.account_uid(), make_account_info(), now_utc=now,
                      profile_name="VantageDemo", broker="Vantage", currency="USD")
        # Window start should be now - 7 days.
        expected = now - timedelta(days=7)
        self.assertIsNotNone(fake.last_from)
        self.assertLessEqual(abs((fake.last_from - expected).total_seconds()), 1)


class TestReasonClassifier(unittest.TestCase):
    def test_classify_reason_mapping(self):
        self.assertEqual(classify_reason(1), "CLOSED_SL")
        self.assertEqual(classify_reason(2), "CLOSED_TP")
        self.assertEqual(classify_reason(3), "CLOSED_STOP_OUT")
        self.assertEqual(classify_reason(4), "CLOSED_MANUAL_DESKTOP")
        self.assertEqual(classify_reason(7), "CLOSED_EXPERT")
        self.assertEqual(classify_reason(12), "CLOSED_MANUAL_MOBILE")
        self.assertEqual(classify_reason(13), "CLOSED_MANUAL_WEB")
        self.assertIsNone(classify_reason(999))
        self.assertIsNone(classify_reason(None))


if __name__ == "__main__":
    unittest.main()
