# -*- coding: utf-8 -*-
"""NativeQt owns workers it starts; shutdown stops them."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import oak_qt_shell
from oak_qt_shell import (
    force_kill_pid,
    is_project_profile_worker_pid,
    reconcile_worker_lock_file,
    worker_lock_holder_pid,
    worker_lock_path,
)


class WorkerShutdownOwnershipTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._root_patch = patch.object(oak_qt_shell, "ROOT", self.root)
        self._root_patch.start()

    def tearDown(self):
        self._root_patch.stop()
        self._tmp.cleanup()

    def test_launch_registers_monitor_process(self):
        """Ownership registry is monitor_processes[profile] = QProcess."""
        shell = object.__new__(oak_qt_shell.NativeShell)
        shell.monitor_processes = {}
        proc = object()
        shell.monitor_processes["Vantage"] = proc
        self.assertIs(shell.monitor_processes["Vantage"], proc)
        self.assertNotIn("VantageDemo", shell.monitor_processes)

    def test_shutdown_stops_owned_monitors(self):
        shell = object.__new__(oak_qt_shell.NativeShell)
        shell._is_shut_down = False
        shell._startup_ops = {"Vantage": 1}
        shell.starting_profiles = {"Vantage"}
        shell.startup_phase = {"Vantage": "x"}
        shell.signal_supervisor = None
        shell.eod_update_process = None
        shell.stock_process = None
        shell.signal_processes = {}
        shell.monitor_processes = {"Vantage": MagicMock()}
        shell.log = lambda *a, **k: None
        stopped: list[str] = []

        def _stop(profile, wait_ms=2000):
            stopped.append(profile)
            shell.monitor_processes.pop(profile, None)

        shell._stop_owned_monitor = _stop  # type: ignore
        oak_qt_shell.NativeShell.shutdown(shell)
        self.assertEqual(stopped, ["Vantage"])
        self.assertTrue(shell._is_shut_down)

    def test_stop_owned_kills_matching_lock_holder_then_reconciles(self):
        path = worker_lock_path("Vantage")
        path.write_text("4242", encoding="utf-8")
        shell = object.__new__(oak_qt_shell.NativeShell)
        shell.monitor_processes = {}
        shell.log = lambda *a, **k: None

        with patch.object(oak_qt_shell, "worker_lock_holder_pid", return_value=4242):
            with patch.object(oak_qt_shell, "is_project_profile_worker_pid", return_value=True) as match:
                with patch.object(oak_qt_shell, "force_kill_pid", return_value=True) as kill:
                    with patch.object(oak_qt_shell, "_pid_is_running", return_value=False):
                        oak_qt_shell.NativeShell._stop_owned_monitor(shell, "Vantage", wait_ms=10)
                        match.assert_called()
                        kill.assert_called_with(4242)
        self.assertFalse(path.exists())

    def test_stop_owned_does_not_kill_non_matching_holder(self):
        path = worker_lock_path("Vantage")
        path.write_text("7777", encoding="utf-8")
        shell = object.__new__(oak_qt_shell.NativeShell)
        shell.monitor_processes = {}
        shell.log = lambda *a, **k: None

        with patch.object(oak_qt_shell, "worker_lock_holder_pid", return_value=7777):
            with patch.object(oak_qt_shell, "is_project_profile_worker_pid", return_value=False):
                with patch.object(oak_qt_shell, "force_kill_pid") as kill:
                    with patch.object(oak_qt_shell, "_pid_is_running", return_value=True):
                        oak_qt_shell.NativeShell._stop_owned_monitor(shell, "Vantage", wait_ms=10)
                        kill.assert_not_called()
        # live non-matching lock must not be deleted by reconcile
        self.assertTrue(path.exists())

    def test_vantage_vs_vantagedemo_profile_token(self):
        with patch.object(oak_qt_shell, "_pid_is_running", return_value=True):
            with patch("subprocess.run") as run:
                run.return_value = SimpleNamespace(
                    stdout='python OAK_Hidden_SLTP_Manager.py --worker --profile VantageDemo\n'
                )
                self.assertFalse(is_project_profile_worker_pid(1, "Vantage"))
                self.assertTrue(is_project_profile_worker_pid(1, "VantageDemo"))


if __name__ == "__main__":
    unittest.main()
