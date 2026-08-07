# -*- coding: utf-8 -*-
"""Tests for AccountAuditService — checkpoint scheduling, catch-up, sampling.

Verifies §2 (checkpoint schedule), §6 (reconstruction), §7 (sampler isolation)
and the "no candle API" constraint of the audit runtime.
"""
import fnmatch
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
from services.mt5_deal_reconciler import MT5DealReconciler
from services.checkpoint_engine import CheckpointEngine
from services.equity_sampler import EquitySampler
from services.account_audit_service import (
    AccountAuditService,
    broker_time_from_mt5,
    account_info_dict,
    CHECKPOINT_HOURS_ORDERED,
)


def make_account_info(**overrides):
    info = {
        "login": 12345, "server": "Vantage-Server", "currency": "USD",
        "account_type": "demo", "balance": 10000.0, "equity": 10050.0,
        "margin": 500.0, "margin_free": 9550.0, "margin_level": 2010.0,
        "profit": 50.0, "credit": 0.0, "profile_name": "VantageDemo",
        "broker": "Vantage",
    }
    info.update(overrides)
    return info


class FakeMT5:
    def __init__(self, tick_time=None, account=None, tick_times=None, symbols=None):
        self.tick_time = tick_time
        self.account = account or SimpleNamespace(**make_account_info())
        self.copy_rates_calls = 0
        #: Per-symbol tick epochs. When non-empty this takes precedence over
        #: ``tick_time`` and models a broker where only some symbols tick.
        self.tick_times = dict(tick_times or {})
        #: Symbol names visible to ``symbols_get`` group probes.
        self.symbols = list(symbols or [])
        self.tick_calls = []
        self.symbols_get_groups = []

    def symbol_info_tick(self, symbol):
        self.tick_calls.append(symbol)
        if self.tick_times:
            epoch = self.tick_times.get(symbol)
            return None if epoch is None else SimpleNamespace(time=epoch)
        if self.tick_time is None:
            return None
        return SimpleNamespace(time=self.tick_time)

    def symbols_get(self, group=None):
        self.symbols_get_groups.append(group)
        return tuple(
            SimpleNamespace(name=name)
            for name in self.symbols
            if group is None or fnmatch.fnmatch(name, group)
        )

    def account_info(self):
        return self.account

    def positions_get(self, symbol=None):
        return []

    def copy_rates_from_pos(self, *a, **k):
        self.copy_rates_calls += 1
        return None

    def copy_rates_range(self, *a, **k):
        self.copy_rates_calls += 1
        return None


class AuditServiceTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="robot-sltp-audit-svc-")
        self.db_path = os.path.join(self._tmpdir.name, "trade_audit.db")
        self.store = TradeAuditStore(db_path=self.db_path, read_only=True)
        self.mt5 = FakeMT5()
        self.reconciler = MT5DealReconciler(self.store, self.mt5)
        self.engine = CheckpointEngine(self.store, self.reconciler)
        self.sampler = EquitySampler(self.store, interval_seconds=60)
        self.publisher = SimpleNamespace(pushed=0)

        def fake_push_all(account_uid):
            self.publisher.pushed += 1
            return {"pushed": True, "results": {}}

        self.publisher.push_all = fake_push_all
        self.account_uid = "12345@Vantage-Server"
        self.service = None

    def tearDown(self):
        if self.store:
            self.store.close()
        self._tmpdir.cleanup()

    def make_service(self, broker_dt, tick_interval=30, sample_interval=60):
        return AccountAuditService(
            self.store,
            self.account_uid,
            broker_time_provider=lambda: broker_dt,
            account_info_provider=lambda: account_info_dict(self.mt5.account, profile_name="VantageDemo", broker="Vantage"),
            positions_provider=lambda: self.mt5.positions_get(),
            reconciler=self.reconciler,
            engine=self.engine,
            sampler=self.sampler,
            publisher=self.publisher,
            profile_name="VantageDemo",
            broker="Vantage",
            currency="USD",
            tick_interval_seconds=tick_interval,
            sample_interval_seconds=sample_interval,
        )

    def _account_id(self):
        return self.store.upsert_account(
            account_uid=self.account_uid, profile_name="VantageDemo",
            broker="Vantage", server="Vantage-Server", currency="USD",
        )


class TestBrokerTimeHelpers(AuditServiceTestCase):
    def test_broker_time_from_mt5_tick(self):
        # Roundtrip local time: naive datetime -> epoch -> fromtimestamp must
        # preserve the wall-clock hour on any machine timezone (UTC, UTC+7, ...).
        naive = datetime(2026, 8, 4, 7, 0, 0)
        self.mt5.tick_time = int(naive.timestamp())
        dt = broker_time_from_mt5(self.mt5)
        self.assertEqual(dt.hour, 7)
        self.assertEqual(dt.date().isoformat(), "2026-08-04")
        # Exact symbol answered -> no alias/discovery probing at all.
        self.assertEqual(self.mt5.tick_calls, ["XAUUSD"])
        self.assertEqual(self.mt5.symbols_get_groups, [])

    def test_broker_time_none_when_no_tick(self):
        self.assertIsNone(broker_time_from_mt5(self.mt5))

    def test_broker_time_recovers_from_suffixed_symbol(self):
        # Vantage-style broker: plain XAUUSD does not tick, XAUUSD+ does.
        naive = datetime(2026, 8, 4, 7, 0, 0)
        self.mt5.tick_times = {"XAUUSD+": int(naive.timestamp())}
        dt = broker_time_from_mt5(self.mt5)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.hour, 7)
        self.assertEqual(dt.date().isoformat(), "2026-08-04")
        # The requested symbol must still be attempted first.
        self.assertEqual(self.mt5.tick_calls[0], "XAUUSD")
        self.assertEqual(self.mt5.tick_calls[-1], "XAUUSD+")

    def test_broker_time_discovers_symbol_via_bounded_group_probe(self):
        naive = datetime(2026, 8, 4, 16, 0, 0)
        self.mt5.tick_times = {"XAUUSD.m": int(naive.timestamp())}
        self.mt5.symbols = ["EURUSD", "XAUUSD.m"]
        dt = broker_time_from_mt5(self.mt5)
        self.assertIsNotNone(dt)
        self.assertEqual(dt.hour, 16)
        # Discovery stays bounded to gold groups and never probes EURUSD.
        self.assertEqual(self.mt5.tick_calls[0], "XAUUSD")
        self.assertTrue(set(self.mt5.symbols_get_groups).issubset({"*XAUUSD*", "*GOLD*"}))
        self.assertNotIn("EURUSD", self.mt5.tick_calls)

    def test_broker_time_probes_each_symbol_once(self):
        # Discovery re-reporting an already-tried alias must not re-probe it.
        self.mt5.tick_times = {"EURUSD": 1}
        self.mt5.symbols = ["XAUUSD+", "XAUUSD+"]
        self.assertIsNone(broker_time_from_mt5(self.mt5))
        self.assertEqual(self.mt5.tick_calls.count("XAUUSD+"), 1)
        self.assertEqual(self.mt5.tick_calls.count("XAUUSD"), 1)

    def test_broker_time_none_when_no_gold_symbol_exists(self):
        self.mt5.tick_times = {"EURUSD": 1}
        self.mt5.symbols = []
        self.assertIsNone(broker_time_from_mt5(self.mt5))
        self.assertIn("*XAUUSD*", self.mt5.symbols_get_groups)

    def test_broker_time_none_when_tick_api_missing(self):
        self.assertIsNone(broker_time_from_mt5(SimpleNamespace()))

    def test_broker_time_none_when_symbols_get_missing(self):
        stub = SimpleNamespace(symbol_info_tick=lambda symbol: None)
        self.assertIsNone(broker_time_from_mt5(stub))

    def test_broker_time_none_when_apis_raise(self):
        def boom(*a, **k):
            raise RuntimeError("terminal not connected")

        self.mt5.symbol_info_tick = boom
        self.mt5.symbols_get = boom
        self.assertIsNone(broker_time_from_mt5(self.mt5))

    def test_broker_time_rejects_never_ticked_zero_epoch(self):
        # A symbol present but never ticked reports time=0; using it would
        # date the broker clock to 1970 and fire bogus checkpoints.
        self.mt5.tick_times = {"XAUUSD": 0}
        self.assertIsNone(broker_time_from_mt5(self.mt5))

    def test_account_info_dict_maps_mt5_fields(self):
        d = account_info_dict(self.mt5.account, profile_name="VantageDemo", broker="Vantage")
        self.assertEqual(d["free_margin"], 9550.0)   # MT5 margin_free -> free_margin
        self.assertEqual(d["open_profit"], 50.0)     # MT5 profit -> open_profit
        self.assertEqual(d["profile_name"], "VantageDemo")
        self.assertEqual(d["server"], "Vantage-Server")


class TestCheckpointScheduling(AuditServiceTestCase):
    def test_h3_opens_interval_when_clock_reaches_h3(self):
        broker_dt = datetime(2026, 8, 4, 3, 30)
        svc = self.make_service(broker_dt)
        result = svc.tick()
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["checkpoints_run"], 1)

        account_id = self._account_id()
        run = self.store.get_checkpoint_run(account_id, "2026-08-04", 3)
        self.assertIsNotNone(run)
        self.assertEqual(run["status"], "NO_OPEN_POSITIONS")  # no positions
        self.assertEqual(result["reconstructed"], 0)
        self.assertGreaterEqual(self.publisher.pushed, 1)

    def test_h7_closes_h3_interval_when_clock_reaches_h7(self):
        svc = self.make_service(datetime(2026, 8, 4, 3, 30))
        svc.tick()
        svc = self.make_service(datetime(2026, 8, 4, 7, 30))
        result = svc.tick()

        account_id = self._account_id()
        h3 = self.store.get_checkpoint_run(account_id, "2026-08-04", 3)
        h7 = self.store.get_checkpoint_run(account_id, "2026-08-04", 7)
        self.assertIsNotNone(h7)
        self.assertEqual(h7["status"], "NO_OPEN_POSITIONS")
        # H3 was already captured -> not re-run, not reconstructed.
        self.assertEqual(result["checkpoints_run"], 1)
        self.assertEqual(result["reconstructed"], 0)
        self.assertEqual(h3["status"], "NO_OPEN_POSITIONS")

    def test_checkpoint_is_idempotent_across_ticks(self):
        svc = self.make_service(datetime(2026, 8, 4, 3, 30))
        svc.tick()
        svc.tick()  # same broker time again
        account_id = self._account_id()
        runs = self.store.list_checkpoint_runs(account_id)
        self.assertEqual(len(runs), 1)

    def test_missed_earlier_hours_are_reconstructed(self):
        # App starts at 09:30 — H3 and H7 of today were missed.
        svc = self.make_service(datetime(2026, 8, 4, 9, 30))
        result = svc.tick()

        account_id = self._account_id()
        h3 = self.store.get_checkpoint_run(account_id, "2026-08-04", 3)
        h7 = self.store.get_checkpoint_run(account_id, "2026-08-04", 7)
        h9 = self.store.get_checkpoint_run(account_id, "2026-08-04", 9)
        # H3 + H7 reconstructed (missed), H9 run normally.
        self.assertEqual(h3["capture_mode"], "RECONSTRUCTED")
        self.assertEqual(h7["capture_mode"], "RECONSTRUCTED")
        self.assertEqual(h9["capture_mode"], "NORMAL")
        self.assertEqual(result["reconstructed"], 2)
        self.assertEqual(result["checkpoints_run"], 1)


class TestEquitySampling(AuditServiceTestCase):
    def test_equity_sampler_records_account_state(self):
        svc = self.make_service(datetime(2026, 8, 4, 3, 30))
        now = datetime(2026, 8, 4, 3, 30, tzinfo=timezone.utc)
        svc.tick(now_utc=now)

        account_id = self._account_id()
        samples = self.store.list_equity_samples(account_id)
        self.assertEqual(len(samples), 1)
        self.assertEqual(samples[0]["equity"], 10050.0)
        self.assertEqual(samples[0]["balance"], 10000.0)

    def test_sampler_respects_interval(self):
        svc = self.make_service(datetime(2026, 8, 4, 3, 30), sample_interval=60)
        t0 = datetime(2026, 8, 4, 3, 30, tzinfo=timezone.utc)
        svc.tick(now_utc=t0)
        # 30s later — inside interval, no new sample.
        svc.tick(now_utc=t0 + timedelta(seconds=30))
        account_id = self._account_id()
        self.assertEqual(len(self.store.list_equity_samples(account_id)), 1)
        # 60s later — new sample.
        svc.tick(now_utc=t0 + timedelta(seconds=60))
        self.assertEqual(len(self.store.list_equity_samples(account_id)), 2)


class TestNoCandleApi(AuditServiceTestCase):
    def test_no_mt5_copy_rates_called_in_account_audit_mode(self):
        svc = self.make_service(datetime(2026, 8, 4, 3, 30))
        svc.tick()
        svc = self.make_service(datetime(2026, 8, 4, 7, 30))
        svc.tick()
        svc = self.make_service(datetime(2026, 8, 4, 9, 30))
        svc.tick()
        # The audit runtime must never call candle APIs.
        self.assertEqual(self.mt5.copy_rates_calls, 0)


class TestFailureIsolation(AuditServiceTestCase):
    def test_no_broker_clock_does_not_crash(self):
        svc = self.make_service(None)
        result = svc.tick()
        self.assertEqual(result["status"], "NO_BROKER_CLOCK")

    def test_no_account_info_does_not_crash(self):
        svc = AccountAuditService(
            self.store, self.account_uid,
            broker_time_provider=lambda: datetime(2026, 8, 4, 3, 30),
            account_info_provider=lambda: {},
            reconciler=self.reconciler, engine=self.engine,
        )
        result = svc.tick()
        self.assertEqual(result["status"], "NOT_CONNECTED")

    def test_sampler_failure_does_not_stop_loop(self):
        svc = self.make_service(datetime(2026, 8, 4, 3, 30))
        original = self.sampler.sample_once

        def broken_sample_once(*a, **k):
            raise RuntimeError("MT5 disconnected")

        self.sampler.sample_once = broken_sample_once
        try:
            result = svc.tick()
        finally:
            self.sampler.sample_once = original
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["checkpoints_run"], 1)


if __name__ == "__main__":
    unittest.main()
