# -*- coding: utf-8 -*-
"""Multi-monitor policy unit tests (no GUI spawn)."""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

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
        self.running_monitors_frame = None

    def log(self, msg):
        self.logs.append(msg)

    def after(self, ms, fn, *args):
        pass

    def update_ui_state(self, name):
        self._last_ui = name

    def refresh_profile_list(self):
        pass

    def refresh_running_monitors_panel(self):
        self._panel_refreshed = True

    def _update_active_profile_badge(self, name):
        pass

    def _kill_orphan_workers(self, name):
        self.logs.append(f"orphan:{name}")


class TestMultiMonitor(unittest.TestCase):
    def test_live_list_multiple(self):
        app = FakeApp()
        app.workers = {
            "A": {"proc": FakeProc(True, 11)},
            "B": {"proc": FakeProc(True, 22)},
            "C": {"proc": FakeProc(False, 33)},
        }
        live = app._get_live_running_profiles()
        self.assertEqual(live, ["A", "B"])

    def test_primary_prefers_selected_if_live(self):
        app = FakeApp()
        app.workers = {
            "A": {"proc": FakeProc(True, 11)},
            "B": {"proc": FakeProc(True, 22)},
        }
        app.combo_profiles.get.return_value = "B"
        self.assertEqual(app._get_live_running_profile(), "B")

    def test_stop_profile_only_targets_one(self):
        app = FakeApp()
        a_proc = FakeProc(True, 11)
        b_proc = FakeProc(True, 22)
        app.workers = {
            "A": {"proc": a_proc},
            "B": {"proc": b_proc},
        }
        app.running_profile_name = "A"

        a_proc.terminate = MagicMock(side_effect=lambda: setattr(a_proc, "_alive", False))
        with patch.object(os, "name", "posix"):
            app.stop_monitor_profile("A", confirm=False)

        self.assertFalse(app._is_profile_live("A"))
        self.assertTrue(app._is_profile_live("B"))
        self.assertEqual(app.running_profile_name, "B")


if __name__ == "__main__":
    unittest.main()
