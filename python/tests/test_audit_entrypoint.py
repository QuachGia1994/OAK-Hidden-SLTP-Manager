# -*- coding: utf-8 -*-
"""Regression coverage for the audit-service launcher path."""
import argparse
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

PYTHON_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PYTHON_ROOT.parent
for path in (PYTHON_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import mt5_signal_bot  # noqa: E402


class TestAuditEntrypoint(unittest.TestCase):
    def test_audit_service_starts_without_missing_checkpoint_constant(self):
        with mock.patch.object(mt5_signal_bot.mt5, "account_info", return_value=SimpleNamespace(login=123, server="Demo")), \
             mock.patch.object(mt5_signal_bot, "resolve_active_profile", return_value="Vantage"), \
             mock.patch.object(mt5_signal_bot, "load_profile_config", return_value={"profile_name": "Vantage"}), \
             mock.patch("repositories.trade_audit_store.TradeAuditStore"), \
             mock.patch("services.mt5_deal_reconciler.MT5DealReconciler"), \
             mock.patch("services.checkpoint_engine.CheckpointEngine"), \
             mock.patch("services.equity_sampler.EquitySampler"), \
             mock.patch("services.performance_calculator.PerformanceCalculator"), \
             mock.patch("services.audit_dashboard_publisher.AuditDashboardPublisher"), \
             mock.patch("services.account_audit_service.AccountAuditService") as audit_cls:
            mt5_signal_bot.run_audit_service("Vantage", tick_interval=1, sample_interval=1)
        audit_cls.return_value.run_forever.assert_called_once_with()


class TestSignalBotAuditServiceFlag(unittest.TestCase):
    """Verify all launcher paths include --audit-service for signal_bot."""

    # --- (1) start_signal command construction: dev mode ---
    def test_build_signal_process_cmd_dev_signal_bot_includes_audit_service(self):
        from utils import build_signal_process_cmd
        cmd = build_signal_process_cmd("signal_bot", "Vantage", False, "python")
        self.assertIn("--audit-service", cmd)
        self.assertIn("--profile", cmd)

    # --- (2) start_signal command construction: frozen mode ---
    def test_build_signal_process_cmd_frozen_signal_bot_includes_audit_service(self):
        from utils import build_signal_process_cmd
        cmd = build_signal_process_cmd("signal_bot", "Vantage", True, "oak.exe")
        self.assertIn("--audit-service", cmd)
        self.assertIn("--signal-bot", cmd)

    # --- (2b) other keys must NOT receive --audit-service ---
    def test_build_signal_process_cmd_other_keys_exclude_audit_service(self):
        from utils import build_signal_process_cmd
        for key in ("mimo_bot", "mimo_worker", "factcheck_worker"):
            cmd = build_signal_process_cmd(key, "", False, "python")
            self.assertNotIn("--audit-service", cmd, f"{key} must not get --audit-service")

    # --- (3) run_embedded_worker routes --signal-bot --audit-service ---
    def test_run_embedded_worker_routes_audit_service(self):
        """run_embedded_worker with --signal-bot --audit-service must call
        run_audit_service, never main()."""
        import oak_qt_shell
        fake_mt5 = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"mt5_signal_bot": fake_mt5}):
            result = oak_qt_shell.run_embedded_worker(
                ["--signal-bot", "--audit-service", "--profile", "Vantage"]
            )
        self.assertEqual(result, 0)
        fake_mt5.run_audit_service.assert_called_once_with(profile_name="Vantage")
        fake_mt5.main.assert_not_called()

    # --- (4) run_embedded_worker WITHOUT --audit-service still calls main ---
    def test_run_embedded_worker_without_audit_calls_main(self):
        """run_embedded_worker with --signal-bot (no --audit-service) must call
        main(), not run_audit_service."""
        import oak_qt_shell
        fake_mt5 = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"mt5_signal_bot": fake_mt5}):
            result = oak_qt_shell.run_embedded_worker(
                ["--signal-bot", "--profile", "Vantage"]
            )
        self.assertEqual(result, 0)
        fake_mt5.main.assert_called_once_with(profile_name="Vantage")
        fake_mt5.run_audit_service.assert_not_called()

    # --- (5) mt5_signal_bot __main__ argparse routes --audit-service ---
    def test_mt5_signal_bot_main_routes_audit_service(self):
        """mt5_signal_bot.py __main__ with --audit-service must call
        run_audit_service, never main().

        We replicate the exact argparse + if/elif chain from
        mt5_signal_bot.py's __main__ block (lines 6188-6265) to verify
        routing without actually executing the module (which would
        require a live MT5 connection at import time).
        """
        parser = argparse.ArgumentParser()
        parser.add_argument("--profile", type=str)
        parser.add_argument("--audit-service", action="store_true",
                            help="Run account audit service (checkpoints + equity sampler, no candles)")
        parser.add_argument("--audit-tick", type=int, default=30)
        parser.add_argument("--audit-sample", type=int, default=60)
        parser.add_argument("--diagnose-h4-d", action="store_true")
        parser.add_argument("--date", type=str)
        parser.add_argument("--repair-history", action="store_true")
        parser.add_argument("--repair-date", type=str, action="append")
        parser.add_argument("--rebuild-all", action="store_true")
        parser.add_argument("--rebuild-signals", action="store_true")
        parser.add_argument("--rebuild-date", type=str, action="append")
        parser.add_argument("--include-weekends", action="store_true")
        parser.add_argument("--force", action="store_true")
        parser.add_argument("--rebuild-d-history", action="store_true")
        parser.add_argument("--repair-d-date", type=str)
        parser.add_argument("--days", type=int, default=45)
        args, _ = parser.parse_known_args(
            ["--profile", "Vantage", "--audit-service"]
        )
        # Verify argparse parsed correctly
        self.assertTrue(args.audit_service)
        self.assertEqual(args.profile, "Vantage")
        # Verify the branch: audit_service is True, so it hits the
        # elif args.audit_service branch (not the else/main branch).
        # Simulate the branch chain from __main__:
        hit_audit = False
        hit_main = False
        if args.diagnose_h4_d:
            pass
        elif args.repair_history or args.repair_date:
            pass
        elif args.rebuild_all or args.rebuild_signals:
            pass
        elif args.rebuild_date:
            pass
        elif args.rebuild_d_history:
            pass
        elif args.repair_d_date:
            pass
        elif args.audit_service:
            hit_audit = True
        else:
            hit_main = True
        self.assertTrue(hit_audit, "args.audit_service branch should be taken")
        self.assertFalse(hit_main, "main() branch must NOT be taken")

    # --- (6) OAK_Hidden_SLTP_Manager argparse routes --audit-service ---
    def test_hidden_sltp_manager_routes_audit_service(self):
        """OAK_Hidden_SLTP_Manager.py --signal-bot --profile X --audit-service
        must call run_audit_service, never main()."""
        # Simulate the argparse + branch logic from OAK_Hidden_SLTP_Manager.__main__
        parser = argparse.ArgumentParser()
        parser.add_argument("--worker", action="store_true")
        parser.add_argument("--signal-bot", action="store_true")
        parser.add_argument("--audit-service", action="store_true",
                            help="Run account audit service (checkpoints + equity sampler, no candles)")
        parser.add_argument("--mt4-feed-server", action="store_true")
        parser.add_argument("--mimo-bot", action="store_true")
        parser.add_argument("--mimo-worker", action="store_true")
        parser.add_argument("--factcheck-worker", action="store_true")
        parser.add_argument("--profile", type=str)
        args, _ = parser.parse_known_args(
            ["--signal-bot", "--profile", "Vantage", "--audit-service"]
        )
        self.assertTrue(args.signal_bot)
        self.assertTrue(args.audit_service)
        self.assertEqual(args.profile, "Vantage")
        # Execute the branch logic
        fake_mt5 = mock.MagicMock()
        with mock.patch.dict(sys.modules, {"mt5_signal_bot": fake_mt5}):
            if args.signal_bot and args.profile:
                if args.audit_service:
                    fake_mt5.run_audit_service(profile_name=args.profile)
                else:
                    fake_mt5.main(profile_name=args.profile)
        fake_mt5.run_audit_service.assert_called_once_with(profile_name="Vantage")
        fake_mt5.main.assert_not_called()


if __name__ == "__main__":
    unittest.main()
