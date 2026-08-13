# -*- coding: utf-8 -*-
"""NativeQt worker lock hygiene after Stop / forced kill."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import oak_qt_shell
from oak_qt_shell import reconcile_worker_lock_file, worker_lock_path


class ReconcileWorkerLockTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._root_patch = patch.object(oak_qt_shell, "ROOT", self.root)
        self._root_patch.start()

    def tearDown(self):
        self._root_patch.stop()
        self._tmp.cleanup()

    def test_stale_dead_pid_lock_is_removed(self):
        path = worker_lock_path("Vantage")
        path.write_text("22396", encoding="utf-8")
        with patch.object(oak_qt_shell, "_pid_is_running", return_value=False):
            self.assertTrue(reconcile_worker_lock_file("Vantage"))
        self.assertFalse(path.exists())

    def test_live_lock_is_not_removed(self):
        path = worker_lock_path("Vantage")
        path.write_text("99901", encoding="utf-8")
        with patch.object(oak_qt_shell, "_pid_is_running", return_value=True):
            self.assertFalse(reconcile_worker_lock_file("Vantage"))
        self.assertTrue(path.exists())
        self.assertEqual(path.read_text(encoding="utf-8").strip(), "99901")

    def test_missing_lock_is_idempotent(self):
        with patch.object(oak_qt_shell, "_pid_is_running", return_value=False):
            self.assertFalse(reconcile_worker_lock_file("Vantage"))

    def test_corrupt_lock_is_removed(self):
        path = worker_lock_path("VantageDemo")
        path.write_text("not-a-pid", encoding="utf-8")
        with patch.object(oak_qt_shell, "_pid_is_running", return_value=False):
            self.assertTrue(reconcile_worker_lock_file("VantageDemo"))
        self.assertFalse(path.exists())

    def test_worker_done_reconciles_stale_lock(self):
        path = worker_lock_path("Vantage")
        path.write_text("4242", encoding="utf-8")

        # Minimal NativeShell stand-in invoking the real _worker_done body pattern.
        shell = SimpleNamespace(
            starting_profiles=set(),
            startup_phase={},
            startup_error={},
            monitor_processes={"Vantage": object()},
            logs=[],
        )
        shell.log = shell.logs.append
        shell._refresh_profile_controls = lambda: None

        with patch.object(oak_qt_shell, "_pid_is_running", return_value=False):
            oak_qt_shell.NativeShell._worker_done(shell, "Vantage", 0, shell.monitor_processes["Vantage"])

        self.assertFalse(path.exists())
        self.assertTrue(any("Cleared stale worker lock" in m for m in shell.logs))

    def test_other_profile_lock_untouched(self):
        v = worker_lock_path("Vantage")
        d = worker_lock_path("VantageDemo")
        v.write_text("1", encoding="utf-8")
        d.write_text("2", encoding="utf-8")
        with patch.object(oak_qt_shell, "_pid_is_running", return_value=False):
            reconcile_worker_lock_file("Vantage")
        self.assertFalse(v.exists())
        self.assertTrue(d.exists())


if __name__ == "__main__":
    unittest.main()
