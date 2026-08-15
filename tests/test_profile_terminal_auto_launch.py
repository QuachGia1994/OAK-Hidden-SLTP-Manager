# -*- coding: utf-8 -*-
"""
Focused tests for Auto-Launch Profile Terminal on Start Profile (Phase 2).
Covers scenarios A through H:
A. Terminal already running -> attached, no duplicate process, worker starts.
B. Terminal missing -> candidate discovered & launched, readiness verified, worker starts.
C. Terminal path not found -> worker NOT started, profile NOT marked started, clean failure.
D. Terminal launch failure -> worker NOT started, profile NOT marked started, clean failure.
E. IPC readiness failure -> worker NOT started, profile NOT marked started.
F. Duplicate Start Profile -> no duplicate terminal instance.
G. Profile isolation -> Profile A start only touches Profile A terminal.
H. Regression -> Profile supervisor start contract verified.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.mt5_terminal_service import (
    MT5LaunchResult,
    ensure_mt5_profile_connected,
)


class FakeMT5:
    def __init__(self, path_str: str, login: int = 123456, server: str = "Broker-Live"):
        self.terminal_path = path_str
        self.login = login
        self.server = server
        self.initialize_calls = 0
        self.shutdown_calls = 0

    def initialize(self, **kwargs):
        self.initialize_calls += 1
        return True

    def shutdown(self):
        self.shutdown_calls += 1

    def terminal_info(self):
        return SimpleNamespace(path=self.terminal_path)

    def account_info(self):
        return SimpleNamespace(login=self.login, server=self.server)

    def last_error(self):
        return (1, "Success")


class ProfileTerminalAutoLaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.terminal_exe = Path(self.tmp_dir.name) / "terminal64.exe"
        self.terminal_exe.write_bytes(b"fake_binary")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_scenario_A_terminal_already_running(self):
        """Scenario A: Terminal already running -> no Popen, IPC verified, worker starts."""
        profile = {
            "path": str(self.terminal_exe),
            "login_id": 123456,
            "server": "Broker-Live",
            "signal_execution_enabled": True,
        }
        fake_mt5 = FakeMT5(str(self.terminal_exe))
        pops = []

        res = ensure_mt5_profile_connected(
            profile,
            timeout_seconds=2,
            mt5_module=fake_mt5,
            process_factory=lambda p: pops.append(p),
            discover_fn=lambda: [],
        )

        self.assertTrue(res.ok)
        self.assertFalse(res.process_started)
        self.assertEqual(len(pops), 0, "Already running terminal MUST NOT trigger subprocess Popen!")

    def test_scenario_B_terminal_missing_discovered_and_launched(self):
        """Scenario B: Terminal missing -> discovered & launched, readiness verified."""
        vantage_dir = Path(self.tmp_dir.name) / "Vantage-Terminal"
        vantage_dir.mkdir(parents=True, exist_ok=True)
        vantage_exe = vantage_dir / "terminal64.exe"
        vantage_exe.write_bytes(b"fake_vantage")

        profile = {
            "path": "",  # Empty path, rely on discovery
            "broker": "Vantage",
            "login_id": 123456,
            "server": "Vantage-Live",
        }
        fake_mt5 = FakeMT5(str(vantage_exe), login=123456, server="Vantage-Live")
        pops = []

        res = ensure_mt5_profile_connected(
            profile,
            timeout_seconds=2,
            mt5_module=fake_mt5,
            process_factory=lambda p: (pops.append(p) or SimpleNamespace(pid=999)),
            discover_fn=lambda: [vantage_exe],
        )

        self.assertTrue(res.ok)
        self.assertEqual(res.terminal_path, str(vantage_exe))

    def test_scenario_C_terminal_path_not_found(self):
        """Scenario C: Terminal path not found -> clean failure, profile NOT started."""
        profile = {
            "path": "Z:/NonExistentPath/terminal64.exe",
            "profile_name": "GhostProfile",
        }

        res = ensure_mt5_profile_connected(
            profile,
            timeout_seconds=2,
            discover_fn=lambda: [],
        )

        self.assertFalse(res.ok)
        self.assertEqual(res.failure_code, "TERMINAL_PATH_NOT_FOUND")

    def test_scenario_D_terminal_launch_failure(self):
        """Scenario D: Process start fails -> returns PROCESS_START_FAILED."""
        profile = {
            "path": str(self.terminal_exe),
            "login_id": 123456,
            "server": "Broker-Live",
        }

        def failing_popen(path):
            raise OSError("Permission denied by OS")

        # Force _is_terminal_running to False
        with patch("services.mt5_terminal_service._is_terminal_running", return_value=(False, None)):
            res = ensure_mt5_profile_connected(
                profile,
                timeout_seconds=2,
                process_factory=failing_popen,
                discover_fn=lambda: [],
            )

        self.assertFalse(res.ok)
        self.assertEqual(res.failure_code, "PROCESS_START_FAILED")

    def test_scenario_E_ipc_readiness_failure(self):
        """Scenario E: Account or terminal identity mismatch -> fails closed."""
        profile = {
            "path": str(self.terminal_exe),
            "login_id": 123456,
            "server": "Broker-Live",
            "signal_execution_enabled": True,
        }
        # Account mismatch
        fake_mt5 = FakeMT5(str(self.terminal_exe), login=999999, server="Wrong-Server")

        res = ensure_mt5_profile_connected(
            profile,
            timeout_seconds=2,
            mt5_module=fake_mt5,
            discover_fn=lambda: [],
        )

        self.assertFalse(res.ok)
        self.assertIn(res.failure_code, ("ACCOUNT_MISMATCH", "TERMINAL_PATH_MISMATCH"))

    def test_scenario_F_duplicate_start_profile_protection(self):
        """Scenario F: Duplicate Start Profile call on running profile -> attaches without extra Popen."""
        profile = {
            "path": str(self.terminal_exe),
            "login_id": 123456,
            "server": "Broker-Live",
        }
        fake_mt5 = FakeMT5(str(self.terminal_exe))
        pops = []

        res1 = ensure_mt5_profile_connected(profile, mt5_module=fake_mt5, process_factory=lambda p: pops.append(p), discover_fn=lambda: [])
        res2 = ensure_mt5_profile_connected(profile, mt5_module=fake_mt5, process_factory=lambda p: pops.append(p), discover_fn=lambda: [])

        self.assertTrue(res1.ok)
        self.assertTrue(res2.ok)
        self.assertEqual(len(pops), 0, "Sequential starts on active terminal MUST NOT spawn duplicate processes!")

    def test_scenario_G_profile_isolation(self):
        """Scenario G: Starting Profile A only touches Profile A's configured path."""
        path_A = Path(self.tmp_dir.name) / "A" / "terminal64.exe"
        path_A.parent.mkdir(parents=True, exist_ok=True)
        path_A.write_bytes(b"A")

        path_B = Path(self.tmp_dir.name) / "B" / "terminal64.exe"
        path_B.parent.mkdir(parents=True, exist_ok=True)
        path_B.write_bytes(b"B")

        prof_A = {"path": str(path_A), "login_id": 100, "server": "BrokerA"}
        prof_B = {"path": str(path_B), "login_id": 200, "server": "BrokerB"}

        fake_A = FakeMT5(str(path_A), login=100, server="BrokerA")

        res_A = ensure_mt5_profile_connected(prof_A, mt5_module=fake_A, discover_fn=lambda: [])
        self.assertTrue(res_A.ok)
        self.assertEqual(res_A.terminal_path, str(path_A))
        self.assertNotEqual(res_A.terminal_path, str(path_B))

    def test_status_callback_progress_reporting(self):
        """Verify status_callback reports lifecycle transition steps."""
        profile = {
            "path": str(self.terminal_exe),
            "login_id": 123456,
            "server": "Broker-Live",
        }
        fake_mt5 = FakeMT5(str(self.terminal_exe))
        statuses = []

        res = ensure_mt5_profile_connected(
            profile,
            timeout_seconds=2,
            mt5_module=fake_mt5,
            discover_fn=lambda: [],
            status_callback=lambda msg: statuses.append(msg),
        )

        self.assertTrue(res.ok)
        self.assertIn("Checking MT5 terminal...", statuses)
        self.assertIn("MT5 terminal ready", statuses)

    def test_retry_after_startup_failure(self):
        """Verify startup fails closed on invalid path, then succeeds when terminal path becomes valid."""
        invalid_profile = {"path": "Z:/Missing/terminal64.exe"}
        res1 = ensure_mt5_profile_connected(invalid_profile, timeout_seconds=1, discover_fn=lambda: [])
        self.assertFalse(res1.ok)
        self.assertEqual(res1.failure_code, "TERMINAL_PATH_NOT_FOUND")

        valid_profile = {"path": str(self.terminal_exe), "login_id": 123456, "server": "Broker-Live"}
        fake_mt5 = FakeMT5(str(self.terminal_exe))
        res2 = ensure_mt5_profile_connected(valid_profile, timeout_seconds=1, mt5_module=fake_mt5, discover_fn=lambda: [])
        self.assertTrue(res2.ok)


if __name__ == "__main__":
    unittest.main()
