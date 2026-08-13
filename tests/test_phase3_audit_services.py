# -*- coding: utf-8 -*-
"""Tests for Phase 3 audit services — equity sampler & performance calculator (§7, §8, §9, §16).

Covers:
  - §16 mandatory tests (3 exact names)
  - Supporting regression tests for sampler loop isolation, aggregation,
    drawdown, win/loss, holding time, commissions, cash-flow exclusion
"""
import os
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

_workspace_root = Path(__file__).resolve().parents[1]
if str(_workspace_root) not in sys.path:
    sys.path.insert(0, str(_workspace_root))

from repositories.trade_audit_store import TradeAuditStore
from services.equity_sampler import EquitySampler
from services.performance_calculator import PerformanceCalculator


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #
def _make_account_info(**overrides):
    info = {
        "login": 12345, "server": "Vantage-Server", "currency": "USD",
        "account_type": "demo", "balance": 10000.0, "equity": 10050.0,
        "margin": 500.0, "free_margin": 9550.0, "margin_level": 2010.0,
        "open_profit": 50.0, "credit": 0.0, "profile_name": "VantageDemo",
        "broker": "Vantage",
    }
    info.update(overrides)
    return info


def _make_deal(deal_ticket, position_id, entry_type="OUT", deal_type="SELL",
               volume=0.10, price=2510.0, profit=30.0, commission=-0.5,
               swap=0.0, fee=0.0,
               deal_time_utc="2026-08-04T04:00:00+00:00",
               symbol="XAUUSD", order_ticket=""):
    """Return a dict suitable for store.upsert_deal."""
    epoch = int(datetime.fromisoformat(deal_time_utc).timestamp())
    return {
        "deal_ticket": str(deal_ticket),
        "position_id": str(position_id),
        "order_ticket": str(order_ticket),
        "symbol": symbol,
        "deal_type": deal_type,
        "entry_type": entry_type,
        "reason_raw": "",
        "reason_category": "",
        "volume": volume,
        "price": price,
        "profit": profit,
        "commission": commission,
        "swap": swap,
        "fee": fee,
        "deal_time_utc": deal_time_utc,
        "deal_time_broker": epoch,
        "magic": "88000",
        "comment": "",
    }


def _make_position(position_id, symbol="XAUUSD", direction="SELL",
                   initial_volume=0.10, open_time_utc=None):
    """Return a dict suitable for store.upsert_position."""
    return {
        "position_id": str(position_id),
        "position_ticket": str(position_id),
        "symbol": symbol,
        "direction": direction,
        "magic": "88000",
        "comment": "",
        "open_time_utc": open_time_utc,
        "open_time_broker": "",
        "open_price": 2500.0,
        "initial_volume": initial_volume,
        "source_type": "LIVE",
        "public_trade_id": "",
    }


def _seed_equity_sample(store, account_id, sampled_at_utc, balance, equity,
                        margin=0.0, free_margin=0.0, margin_level=0.0, open_profit=0.0):
    """Insert one equity sample row directly."""
    sample = {
        "sampled_at_utc": sampled_at_utc,
        "sampled_at_broker": sampled_at_utc,
        "balance": balance,
        "equity": equity,
        "margin": margin,
        "free_margin": free_margin,
        "margin_level": margin_level,
        "open_profit": open_profit,
    }
    store.upsert_equity_sample(account_id, sample)


def _seed_snapshot(store, account_id, balance, equity):
    """Insert a checkpoint run + snapshot to produce a snapshot row."""
    run_id = store.upsert_checkpoint_run(
        account_id,
        broker_date="2026-08-04",
        checkpoint_hour=3,
        interval_start="2026-08-03T16:00:00+00:00",
        interval_end="2026-08-04T03:00:00+00:00",
        status="COMPLETED",
    )
    store.upsert_snapshot(run_id, {
        "balance": balance,
        "equity": equity,
        "margin": 0.0,
        "free_margin": 0.0,
        "margin_level": 0.0,
        "open_profit": 0.0,
        "credit": 0.0,
    })


# --------------------------------------------------------------------- #
# Base test case — temp DB
# --------------------------------------------------------------------- #
class Phase3AuditServicesTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="robot-sltp-phase3-")
        self.db_path = os.path.join(self._tmpdir.name, "trade_audit.db")
        self.store = TradeAuditStore(db_path=self.db_path, read_only=True)
        self.account_uid = "12345@Vantage-Server"

    def tearDown(self):
        if self.store:
            self.store.close()
        self._tmpdir.cleanup()

    def _create_account(self):
        return self.store.upsert_account(
            account_uid=self.account_uid, profile_name="VantageDemo",
            broker="Vantage", server="Vantage-Server", currency="USD",
        )


# ===================================================================== #
# §16 MANDATORY TESTS (exact names)
# ===================================================================== #
class TestEquitySamplerRecordsAccountState(Phase3AuditServicesTestCase):
    """§16 — EquitySampler sample_once records account and equity sample."""

    def test_equity_sampler_records_account_state(self):
        sampler = EquitySampler(self.store, interval_seconds=1)
        now = datetime(2026, 8, 4, 10, 0, 0, tzinfo=timezone.utc)
        info = _make_account_info(balance=12000.0, equity=12300.0)

        result = sampler.sample_once(self.account_uid, info, now_utc=now)

        self.assertIn("account_id", result)
        self.assertIn("sample_count", result)
        self.assertGreaterEqual(result["sample_count"], 1)
        self.assertEqual(result["sampled_at_utc"], now.isoformat())

        # Verify stored data
        account = self.store.get_account_by_uid(self.account_uid)
        self.assertIsNotNone(account)
        samples = self.store.list_equity_samples(account_id=account["id"])
        self.assertGreaterEqual(len(samples), 1)
        latest = samples[0]
        self.assertAlmostEqual(latest["balance"], 12000.0)
        self.assertAlmostEqual(latest["equity"], 12300.0)


class TestDrawdownUsesEquitySamples(Phase3AuditServicesTestCase):
    """§16 — Drawdown computed from equity samples when available."""

    def test_drawdown_uses_equity_samples(self):
        account_id = self._create_account()
        # Seed 4 equity samples: 10000, 10500, 9800, 10200
        # Peak before 9800 = 10500, drawdown = 10500 - 9800 = 700
        _seed_equity_sample(store=self.store, account_id=account_id,
                           sampled_at_utc="2026-08-04T00:00:00+00:00",
                           balance=10000.0, equity=10000.0)
        _seed_equity_sample(store=self.store, account_id=account_id,
                           sampled_at_utc="2026-08-04T01:00:00+00:00",
                           balance=10000.0, equity=10500.0)
        _seed_equity_sample(store=self.store, account_id=account_id,
                           sampled_at_utc="2026-08-04T02:00:00+00:00",
                           balance=10000.0, equity=9800.0)
        _seed_equity_sample(store=self.store, account_id=account_id,
                           sampled_at_utc="2026-08-04T03:00:00+00:00",
                           balance=10000.0, equity=10200.0)

        calc = PerformanceCalculator(self.store)
        metrics = calc.compute(self.account_uid)

        self.assertEqual(metrics["drawdown_source"], "EQUITY_SAMPLES")
        self.assertAlmostEqual(metrics["max_equity_drawdown"], 700.0)


class TestCashFlowIsExcludedFromTradingProfit(Phase3AuditServicesTestCase):
    """§16 — Cash flows must NOT be counted as trading profit."""

    def test_cash_flow_is_excluded_from_trading_profit(self):
        account_id = self._create_account()

        # Seed a winning close deal: profit=200
        deal = _make_deal(
            deal_ticket="D1", position_id="P1", entry_type="OUT",
            deal_type="SELL", profit=200.0,
            deal_time_utc="2026-08-04T04:00:00+00:00",
        )
        self.store.upsert_deal(account_id, deal)

        # Seed a cash deposit of 500
        self.store.add_cash_flow(
            account_id, time_utc="2026-08-04T02:00:00+00:00",
            flow_type="DEPOSIT", amount=500.0,
        )

        # Seed equity sample reflecting balance after deposit + profit
        _seed_equity_sample(store=self.store, account_id=account_id,
                           sampled_at_utc="2026-08-04T05:00:00+00:00",
                           balance=10700.0, equity=10700.0)

        calc = PerformanceCalculator(self.store)
        metrics = calc.compute(self.account_uid, initial_balance=10000.0)

        # trading_return = current_balance - initial_balance - net_cash_flow
        # = 10700 - 10000 - 500 = 200 (pure trading profit)
        self.assertAlmostEqual(metrics["trading_return"], 200.0)
        self.assertAlmostEqual(metrics["trading_return_pct"], 0.02)
        self.assertAlmostEqual(metrics["account_growth_pct"], 0.07)
        self.assertAlmostEqual(metrics["realized_pl"], 200.0)
        self.assertAlmostEqual(metrics["net_cash_flow"], 500.0)
        self.assertAlmostEqual(metrics["net_deposits"], 500.0)


# ===================================================================== #
# SUPPORTING TESTS
# ===================================================================== #
class TestSamplerFailureDoesNotStopLoop(Phase3AuditServicesTestCase):
    """Sampler loop isolation: provider raising once must not kill the loop (§7)."""

    def test_sampler_failure_does_not_stop_loop(self):
        call_count = [0]

        def provider():
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("MT5 disconnected")
            return _make_account_info(balance=10000.0, equity=10050.0)

        sampler = EquitySampler(self.store, interval_seconds=0)
        count = sampler.sample_loop(
            self.account_uid, provider, max_iterations=3,
        )
        # First call raises, calls 2 & 3 succeed → 2 samples written.
        self.assertEqual(count, 2)


class TestSamplerSkipsWhenNotConnected(Phase3AuditServicesTestCase):
    """Provider returning None → no sample written."""

    def test_sampler_skips_when_not_connected(self):
        def provider():
            return None

        sampler = EquitySampler(self.store, interval_seconds=0)
        count = sampler.sample_loop(
            self.account_uid, provider, max_iterations=3,
        )
        self.assertEqual(count, 0)
        account = self.store.get_account_by_uid(self.account_uid)
        if account is not None:
            samples = self.store.list_equity_samples(account_id=account["id"])
            self.assertEqual(len(samples), 0)


class TestAggregateSamplesBucketsEquityOhlc(Phase3AuditServicesTestCase):
    """aggregate_samples produces correct OHLC buckets."""

    def test_aggregate_samples_buckets_equity_ohlc(self):
        account_id = self._create_account()
        # Two samples in the same 5-min bucket, one in the next.
        _seed_equity_sample(store=self.store, account_id=account_id,
                           sampled_at_utc="2026-08-04T10:00:00+00:00",
                           balance=10000.0, equity=10000.0)
        _seed_equity_sample(store=self.store, account_id=account_id,
                           sampled_at_utc="2026-08-04T10:02:00+00:00",
                           balance=10000.0, equity=10500.0)
        _seed_equity_sample(store=self.store, account_id=account_id,
                           sampled_at_utc="2026-08-04T10:07:00+00:00",
                           balance=10000.0, equity=10200.0)

        sampler = EquitySampler(self.store, interval_seconds=60)
        buckets = sampler.aggregate_samples(self.account_uid, bucket_minutes=5)

        self.assertEqual(len(buckets), 2)
        # First bucket: open=10000, high=10500, low=10000, close=10500
        b0 = buckets[0]
        self.assertEqual(b0["count"], 2)
        self.assertAlmostEqual(b0["open"], 10000.0)
        self.assertAlmostEqual(b0["high"], 10500.0)
        self.assertAlmostEqual(b0["low"], 10000.0)
        self.assertAlmostEqual(b0["close"], 10500.0)
        # Second bucket: single sample
        b1 = buckets[1]
        self.assertEqual(b1["count"], 1)
        self.assertAlmostEqual(b1["open"], 10200.0)
        self.assertAlmostEqual(b1["close"], 10200.0)


class TestProfitFactorWinRateExpectancy(Phase3AuditServicesTestCase):
    """3 wins + 1 loss → win_rate 0.75, profit_factor, expectancy correct."""

    def test_profit_factor_win_rate_expectancy(self):
        account_id = self._create_account()

        # 3 winning positions (P1, P2, P3) and 1 losing position (P4).
        # Each position gets an IN + OUT deal.
        deals = [
            # P1: win +100
            _make_deal("D1", "P1", entry_type="IN", deal_type="BUY",
                       profit=0.0, deal_time_utc="2026-08-01T00:00:00+00:00"),
            _make_deal("D2", "P1", entry_type="OUT", deal_type="BUY",
                       profit=100.0, commission=-1.0, deal_time_utc="2026-08-01T04:00:00+00:00"),
            # P2: win +200
            _make_deal("D3", "P2", entry_type="IN", deal_type="SELL",
                       profit=0.0, deal_time_utc="2026-08-02T00:00:00+00:00"),
            _make_deal("D4", "P2", entry_type="OUT", deal_type="SELL",
                       profit=200.0, commission=-1.0, deal_time_utc="2026-08-02T04:00:00+00:00"),
            # P3: win +50
            _make_deal("D5", "P3", entry_type="IN", deal_type="BUY",
                       profit=0.0, deal_time_utc="2026-08-03T00:00:00+00:00"),
            _make_deal("D6", "P3", entry_type="INOUT", deal_type="BUY",
                       profit=50.0, commission=-0.5, deal_time_utc="2026-08-03T04:00:00+00:00"),
            # P4: loss -80
            _make_deal("D7", "P4", entry_type="IN", deal_type="SELL",
                       profit=0.0, deal_time_utc="2026-08-04T00:00:00+00:00"),
            _make_deal("D8", "P4", entry_type="OUT_BY", deal_type="SELL",
                       profit=-80.0, commission=-1.0, deal_time_utc="2026-08-04T04:00:00+00:00"),
        ]
        for d in deals:
            self.store.upsert_deal(account_id, d)

        calc = PerformanceCalculator(self.store)
        m = calc.compute(self.account_uid)

        # realized_pl = 100+200+50-80 = 270
        self.assertAlmostEqual(m["realized_pl"], 270.0)
        # gross_profit = 350, gross_loss = 80
        self.assertAlmostEqual(m["gross_profit"], 350.0)
        self.assertAlmostEqual(m["gross_loss"], 80.0)
        # profit_factor = 350/80 = 4.375
        self.assertAlmostEqual(m["profit_factor"], 4.375)
        # win_rate = 3/(3+1) = 0.75, based on decided closed positions.
        self.assertAlmostEqual(m["win_rate"], 0.75)
        self.assertEqual(m["closed_trade_count"], 4)
        self.assertEqual(m["winning_trade_count"], 3)
        self.assertEqual(m["losing_trade_count"], 1)
        self.assertEqual(m["win_rate_basis"], "CLOSED_POSITIONS")
        # average_win = 350/3
        self.assertAlmostEqual(m["average_win"], 350.0 / 3.0)
        # average_loss = 80/1 = 80
        self.assertAlmostEqual(m["average_loss"], 80.0)
        # expectancy = (350-80)/4 = 67.5
        self.assertAlmostEqual(m["expectancy"], 67.5)


class TestMaxEquityDrawdownFromSamples(Phase3AuditServicesTestCase):
    """Equity 10000, 10500, 9800, 10200 → max drawdown 700."""

    def test_max_equity_drawdown_from_samples(self):
        account_id = self._create_account()
        _seed_equity_sample(store=self.store, account_id=account_id,
                           sampled_at_utc="2026-08-04T00:00:00+00:00",
                           balance=10000.0, equity=10000.0)
        _seed_equity_sample(store=self.store, account_id=account_id,
                           sampled_at_utc="2026-08-04T01:00:00+00:00",
                           balance=10000.0, equity=10500.0)
        _seed_equity_sample(store=self.store, account_id=account_id,
                           sampled_at_utc="2026-08-04T02:00:00+00:00",
                           balance=10000.0, equity=9800.0)
        _seed_equity_sample(store=self.store, account_id=account_id,
                           sampled_at_utc="2026-08-04T03:00:00+00:00",
                           balance=10000.0, equity=10200.0)

        calc = PerformanceCalculator(self.store)
        m = calc.compute(self.account_uid)

        self.assertEqual(m["drawdown_source"], "EQUITY_SAMPLES")
        self.assertAlmostEqual(m["max_equity_drawdown"], 700.0)
        # current_drawdown = peak(10500) - last(10200) = 300
        self.assertAlmostEqual(m["current_drawdown"], 300.0)


class TestDrawdownFromCheckpointsWhenNoSamples(Phase3AuditServicesTestCase):
    """Only snapshots → drawdown_source == CHECKPOINT."""

    def test_drawdown_from_checkpoints_when_no_samples(self):
        account_id = self._create_account()
        # Create two checkpoint runs with snapshots.
        _seed_snapshot(self.store, account_id, balance=10000.0, equity=10000.0)
        _seed_snapshot(self.store, account_id, balance=10000.0, equity=10500.0)
        _seed_snapshot(self.store, account_id, balance=10000.0, equity=9800.0)

        calc = PerformanceCalculator(self.store)
        m = calc.compute(self.account_uid)

        self.assertEqual(m["drawdown_source"], "CHECKPOINT")
        # Peak before 9800 = 10500, drawdown = 700
        self.assertAlmostEqual(m["max_equity_drawdown"], 700.0)


class TestConsecutiveWinsLosses(Phase3AuditServicesTestCase):
    """Sequence win,loss,win,win,loss → max_consecutive_wins 2, max_consecutive_losses 1."""

    def test_consecutive_wins_losses(self):
        account_id = self._create_account()

        # 5 positions: W, L, W, W, L
        deals = [
            # P1: win (close at T+1h)
            _make_deal("D1", "P1", entry_type="IN", deal_type="BUY",
                       profit=0.0, deal_time_utc="2026-08-01T00:00:00+00:00"),
            _make_deal("D2", "P1", entry_type="OUT", deal_type="BUY",
                       profit=100.0, deal_time_utc="2026-08-01T01:00:00+00:00"),
            # P2: loss
            _make_deal("D3", "P2", entry_type="IN", deal_type="SELL",
                       profit=0.0, deal_time_utc="2026-08-02T00:00:00+00:00"),
            _make_deal("D4", "P2", entry_type="OUT", deal_type="SELL",
                       profit=-50.0, deal_time_utc="2026-08-02T01:00:00+00:00"),
            # P3: win
            _make_deal("D5", "P3", entry_type="IN", deal_type="BUY",
                       profit=0.0, deal_time_utc="2026-08-03T00:00:00+00:00"),
            _make_deal("D6", "P3", entry_type="OUT", deal_type="BUY",
                       profit=80.0, deal_time_utc="2026-08-03T01:00:00+00:00"),
            # P4: win
            _make_deal("D7", "P4", entry_type="IN", deal_type="SELL",
                       profit=0.0, deal_time_utc="2026-08-04T00:00:00+00:00"),
            _make_deal("D8", "P4", entry_type="INOUT", deal_type="SELL",
                       profit=120.0, deal_time_utc="2026-08-04T01:00:00+00:00"),
            # P5: loss
            _make_deal("D9", "P5", entry_type="IN", deal_type="BUY",
                       profit=0.0, deal_time_utc="2026-08-05T00:00:00+00:00"),
            _make_deal("D10", "P5", entry_type="CLOSEBY", deal_type="BUY",
                       profit=-30.0, deal_time_utc="2026-08-05T01:00:00+00:00"),
        ]
        for d in deals:
            self.store.upsert_deal(account_id, d)

        calc = PerformanceCalculator(self.store)
        m = calc.compute(self.account_uid)

        # Sequence: W, L, W, W, L → max_consecutive_wins=2, max_consecutive_losses=1
        self.assertEqual(m["max_consecutive_wins"], 2)
        self.assertEqual(m["max_consecutive_losses"], 1)


class TestHoldingTimeAndCommissions(Phase3AuditServicesTestCase):
    """Seed IN + OUT deals with times; verify average_holding_time and totals."""

    def test_holding_time_and_commissions(self):
        account_id = self._create_account()

        # P1: IN at T+0, OUT at T+4h → 14400 seconds
        # P2: IN at T+0, OUT at T+6h → 21600 seconds
        deals = [
            _make_deal("D1", "P1", entry_type="IN", deal_type="BUY",
                       profit=0.0, commission=-1.0, swap=-0.5, fee=-0.1,
                       deal_time_utc="2026-08-01T00:00:00+00:00"),
            _make_deal("D2", "P1", entry_type="OUT", deal_type="BUY",
                       profit=100.0, commission=-1.0, swap=-0.5, fee=-0.1,
                       deal_time_utc="2026-08-01T04:00:00+00:00"),
            _make_deal("D3", "P2", entry_type="IN", deal_type="SELL",
                       profit=0.0, commission=-2.0, swap=-1.0, fee=-0.2,
                       deal_time_utc="2026-08-02T00:00:00+00:00"),
            _make_deal("D4", "P2", entry_type="OUT", deal_type="SELL",
                       profit=-50.0, commission=-2.0, swap=-1.0, fee=-0.2,
                       deal_time_utc="2026-08-02T06:00:00+00:00"),
        ]
        for d in deals:
            self.store.upsert_deal(account_id, d)

        calc = PerformanceCalculator(self.store)
        m = calc.compute(self.account_uid)

        # average_holding_time = (14400 + 21600) / 2 = 18000
        self.assertAlmostEqual(m["average_holding_time"], 18000.0)
        # total_commission over all trading deals (4 deals): -1-1-2-2 = -6
        self.assertAlmostEqual(m["total_commission"], -6.0)
        # total_swap: -0.5-0.5-1.0-1.0 = -3.0
        self.assertAlmostEqual(m["total_swap"], -3.0)
        # total_fees: -0.1-0.1-0.2-0.2 = -0.6
        self.assertAlmostEqual(m["total_fees"], -0.6)


class TestEmptyAccountMetricsDoNotRaise(Phase3AuditServicesTestCase):
    """Fresh account → compute() returns dict, no exception."""

    def test_empty_account_metrics_do_not_raise(self):
        account_id = self._create_account()

        calc = PerformanceCalculator(self.store)
        m = calc.compute(self.account_uid)

        # Must return a complete dict with all expected keys.
        self.assertIsInstance(m, dict)
        for key in (
            "current_balance", "current_equity", "net_deposits", "net_profit",
            "realized_pl", "unrealized_pl", "gross_profit", "gross_loss",
            "profit_factor", "win_rate", "average_win", "average_loss",
            "expectancy", "max_consecutive_wins", "max_consecutive_losses",
            "max_equity_drawdown", "max_balance_drawdown", "current_drawdown",
            "recovery_factor", "average_holding_time", "exposure_by_symbol",
            "exposure_by_direction", "total_commission", "total_swap",
            "total_fees", "account_growth", "account_growth_pct", "trading_return",
            "trading_return_pct", "net_cash_flow", "closed_trade_count",
            "winning_trade_count", "losing_trade_count", "win_rate_basis", "drawdown_source",
        ):
            self.assertIn(key, m)
        self.assertEqual(m["drawdown_source"], "NONE")


if __name__ == "__main__":
    unittest.main()
