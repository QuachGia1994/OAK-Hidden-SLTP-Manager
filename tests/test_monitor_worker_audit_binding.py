import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from domain.monitor_worker import MonitorWorker


class MonitorWorkerAuditBindingTests(unittest.TestCase):
    def make_worker(self, profile="ICMarkets"):
        return MonitorWorker(
            {"profile_name": profile, "tele_token": "", "tele_chat": ""},
            lambda _msg: None,
            threading.Event(),
        )

    def test_audit_binding_is_profile_scoped_and_read_only(self):
        worker = self.make_worker("ICMarkets")
        account = SimpleNamespace(login=123, server="ICMarkets-Live", company="IC Markets", currency="USD")
        store = object()
        service = object()

        with patch("repositories.trade_audit_store.TradeAuditStore", return_value=store) as store_cls, \
             patch("services.mt5_deal_reconciler.MT5DealReconciler"), \
             patch("services.checkpoint_engine.CheckpointEngine"), \
             patch("services.equity_sampler.EquitySampler"), \
             patch("services.performance_calculator.PerformanceCalculator"), \
             patch("services.audit_dashboard_publisher.AuditDashboardPublisher"), \
             patch("services.account_audit_service.AccountAuditService", return_value=service):
            self.assertTrue(worker._init_account_audit(account))

        store_cls.assert_called_once_with(read_only=True)
        self.assertIs(worker._audit_service, service)
        self.assertIs(worker._audit_store, store)

    def test_audit_tick_is_throttled(self):
        worker = self.make_worker("Vantage")
        service = SimpleNamespace(tick=lambda: None)
        worker._audit_service = service
        worker._last_audit_tick = 0.0

        with patch("domain.monitor_worker.time.monotonic", return_value=1.0):
            worker._tick_account_audit()
        first_tick = worker._last_audit_tick

        with patch("domain.monitor_worker.time.monotonic", return_value=2.0):
            worker._tick_account_audit()
        self.assertEqual(worker._last_audit_tick, first_tick)
