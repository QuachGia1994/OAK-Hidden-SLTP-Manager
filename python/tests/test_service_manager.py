# -*- coding: utf-8 -*-
"""Tests for the supervisor ServiceManager (start/stop/status lifecycle)."""
import os
import sys
import time
import unittest
from pathlib import Path

PYTHON_ROOT = Path(__file__).resolve().parents[1]  # python/tests -> python
if str(PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(PYTHON_ROOT))
REPO_ROOT = PYTHON_ROOT.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from oak_core.supervisor.services import ServiceManager, SERVICE_SPECS  # noqa: E402


class TestServiceManager(unittest.TestCase):
    def test_registry_has_five_services(self):
        self.assertEqual(
            set(SERVICE_SPECS),
            {"telegram", "mimo_worker", "factcheck_worker", "screener", "signal_bot"},
        )

    def test_list_services_shape(self):
        mgr = ServiceManager()
        res = mgr.list_services()
        self.assertIn("services", res)
        self.assertEqual(len(res["services"]), 5)
        for s in res["services"]:
            for field in ("key", "label", "kind", "configured", "status",
                          "trading_risk", "execution_armed", "scope"):
                self.assertIn(field, s)

    def test_scope_marks_profile_scoped_services(self):
        mgr = ServiceManager()
        self.assertEqual(mgr._status("signal_bot")["scope"], "profile")
        for key in ("telegram", "mimo_worker", "factcheck_worker", "screener"):
            self.assertEqual(mgr._status(key)["scope"], "global", key)
        self.assertEqual(mgr._status("does_not_exist")["scope"], "global")

    def test_on_demand_rejected(self):
        mgr = ServiceManager()
        res = mgr.start_service("screener")
        self.assertFalse(res.get("started"))
        self.assertEqual(res.get("reason"), "on_demand_service")

    def test_clean_exit_is_not_reported_as_crashed(self):
        class FinishedProcess:
            pid = 4242

            @staticmethod
            def poll():
                return 0

        mgr = ServiceManager()
        mgr._procs["telegram"] = FinishedProcess()
        status = mgr.service_status("telegram")
        self.assertEqual(status["status"], "exited")

    def test_critical_requires_confirmation(self):
        mgr = ServiceManager()
        res = mgr.start_service("signal_bot", confirm=False)
        self.assertFalse(res.get("started"))
        self.assertEqual(res.get("reason"), "confirmation_required")
        self.assertEqual(res.get("error"), "CONFIRMATION_REQUIRED")

    def test_signal_bot_audit_flag(self):
        # The "MT5 Account Audit Service" must launch the audit service, not the
        # live trading loop. build_signal_process_cmd now guarantees the flag for
        # signal_bot (single source of truth; ServiceManager appends nothing).
        from utils import build_signal_process_cmd
        cmd = build_signal_process_cmd("signal_bot", "demo", False, sys.executable)
        self.assertIn("--audit-service", cmd)
        self.assertNotIn("main", cmd)  # sanity: it's a flag, not a module

    def test_mimo_worker_start_stop_lifecycle(self):
        # mimo_worker is the safest service (no network/MT5/secrets).
        # When a live external instance already holds mimo_worker.lock (common on
        # developer machines), ServiceManager must refuse a second start rather
        # than skip the entire test.  On a clean CI runner the start/stop path
        # is exercised fully.
        mgr = ServiceManager()
        start = mgr.start_service("mimo_worker")
        time.sleep(0.5)
        st = mgr.service_status("mimo_worker")

        if start.get("reason") == "already_running_lock":
            self.assertFalse(start.get("started"))
            self.assertEqual(start.get("reason"), "already_running_lock")
            # Do not stop a process we do not own.
            return

        if st["status"] != "running":
            mgr.stop_service("mimo_worker")
            self.fail(
                f"mimo_worker did not stay running after start: start={start} status={st}"
            )
        try:
            self.assertTrue(start.get("started"))
            self.assertEqual(start.get("status"), "running")
            self.assertEqual(st["status"], "running")
        finally:
            stop = mgr.stop_service("mimo_worker")
            self.assertTrue(stop.get("stopped"))
            time.sleep(0.3)
            st2 = mgr.service_status("mimo_worker")
            self.assertNotEqual(st2["status"], "running")


if __name__ == "__main__":
    unittest.main()
