# -*- coding: utf-8 -*-
"""Single-monitor policy unit tests (no GUI spawn)."""
import os
import sys
import unittest
from unittest.mock import MagicMock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from controllers.monitor_controller import MonitorControllerMixin


class FakeProc:
    def __init__(self, alive=True, pid=1):
        self._alive = alive
        self.pid = pid

    def poll(self):
        return None if self._alive else 0


class FakeApp(MonitorControllerMixin):
    def __init__(self):
        self.profiles = {"A": {}, "B": {}}
        self.workers = {}
        self.running_profile_name = None
        self.selected_profile_name = None
        self.logs = []
        self.combo_profiles = MagicMock()
        self.combo_profiles.get.return_value = "B"
        self.btn_start = MagicMock()
        self.btn_stop = MagicMock()
        self.console = MagicMock()
        self.copy_console = MagicMock()
        self.copy_console.winfo_exists.return_value = False
        self._warned = []

    def log(self, msg):
        self.logs.append(msg)

    def after(self, ms, fn, *args):
        if callable(fn) and not args:
            try:
                fn()
            except Exception:
                pass

    def update_ui_state(self, name):
        self._last_ui = name

    def refresh_profile_list(self):
        pass

    def _update_active_profile_badge(self, name):
        pass

    def _kill_orphan_workers(self, name):
        pass


class TestSingleMonitor(unittest.TestCase):
    def test_get_live_running_profile(self):
        app = FakeApp()
        app.workers = {"A": {"proc": FakeProc(True, 11)}}
        app.running_profile_name = "A"
        self.assertEqual(app._get_live_running_profile(), "A")

    def test_start_blocked_when_other_running(self):
        app = FakeApp()
        app.workers = {"A": {"proc": FakeProc(True, 11)}}
        app.running_profile_name = "A"
        app.combo_profiles.get.return_value = "B"

        # Patch messagebox
        import controllers.monitor_controller as mc
        import tkinter.messagebox as mb

        warned = []

        def _warn(title, msg):
            warned.append((title, msg))

        old = mb.showwarning
        mb.showwarning = _warn
        try:
            app.start_monitor()
        finally:
            mb.showwarning = old

        self.assertTrue(any("Single Monitor" in t for t, _ in warned) or warned)
        self.assertTrue(any("Start blocked" in x for x in app.logs))
        # A still the only worker
        self.assertIn("A", app.workers)
        self.assertNotIn("B", app.workers)


if __name__ == "__main__":
    unittest.main()
