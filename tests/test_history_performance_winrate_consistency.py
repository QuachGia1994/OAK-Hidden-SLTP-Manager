# -*- coding: utf-8 -*-
"""History closed-trade basis must match Performance win_rate denominator."""
import tempfile
import unittest
from pathlib import Path

from repositories.trade_audit_store import TradeAuditStore
from services.performance_calculator import PerformanceCalculator


class TestHistoryPerformanceWinrateConsistency(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "audit.db"
        self.store = TradeAuditStore(db_path=str(self.db))
        self.uid = "ICMarkets-Demo"
        self.acct_id = self.store.upsert_account(
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

    def _deal(self, ticket, position_id, entry, profit, deal_type="SELL"):
        self.store.upsert_deal(self.acct_id, {
            "deal_ticket": ticket,
            "position_id": position_id,
            "symbol": "GBPJPY+",
            "deal_type": deal_type,
            "entry_type": entry,
            "volume": 0.1,
            "price": 190.0,
            "profit": profit,
            "commission": 0,
            "swap": 0,
            "fee": 0,
            "deal_time_utc": "2026-08-01T10:00:00+00:00",
        })

    def test_multiple_deals_one_position_do_not_inflate_winrate(self):
        # Position A: two OUT deals totaling +50 → one winning closed position
        self._deal("d1", "posA", "IN", 0, "BUY")
        self._deal("d2", "posA", "OUT", 20, "SELL")
        self._deal("d3", "posA", "OUT", 30, "SELL")
        # Position B: losing closed position
        self._deal("d4", "posB", "IN", 0, "BUY")
        self._deal("d5", "posB", "OUT", -10, "SELL")

        calc = PerformanceCalculator(self.store)
        perf = calc.compute(self.uid)

        # Canonical closed-trade basis: 1 win + 1 loss → win_rate 0.5
        self.assertEqual(perf.get("win_rate_basis"), "CLOSED_POSITIONS")
        self.assertEqual(perf.get("winning_trade_count"), 1)
        self.assertEqual(perf.get("losing_trade_count"), 1)
        self.assertEqual(perf.get("closed_trade_count"), 2)
        self.assertAlmostEqual(float(perf.get("win_rate") or 0), 0.5)

        # History aggregation on close deals grouped by position must match
        deals = self.store.list_deals(account_id=self.acct_id)
        close_entry = {"OUT", "INOUT", "OUT_BY", "CLOSEBY"}
        by_pos = {}
        for d in deals:
            if d.get("entry_type") not in close_entry:
                continue
            if d.get("deal_type") not in ("BUY", "SELL"):
                continue
            pid = d.get("position_id") or d.get("deal_ticket")
            by_pos.setdefault(pid, 0.0)
            by_pos[pid] += float(d.get("profit") or 0)
        wins = sum(1 for v in by_pos.values() if v > 0)
        losses = sum(1 for v in by_pos.values() if v < 0)
        self.assertEqual(wins, perf.get("winning_trade_count"))
        self.assertEqual(losses, perf.get("losing_trade_count"))
        denom = wins + losses
        hist_wr = wins / denom if denom else 0.0
        self.assertAlmostEqual(hist_wr, float(perf.get("win_rate") or 0))


if __name__ == "__main__":
    unittest.main()
