# -*- coding: utf-8 -*-
"""select_profile atomic state tests (no GUI)."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from controllers.profile_controller import ProfileControllerMixin


class FakeApp(ProfileControllerMixin):
    """Minimal stand-in with ProfileControllerMixin."""

    def __init__(self):
        self.profiles = {
            "A": {"path": "/a", "profile_name": "A", "tele_chat": "1"},
            "B": {"path": "/b", "profile_name": "B", "tele_chat": "2"},
        }
        self.selected_profile_name = None
        self.running_profile_name = None
        self.config = {}
        self.copy_manager = None
        self.workers = {}
        self.entries = None  # no form
        self.list_frame = None
        self._last_json_mtime = 0
        self._selecting_profile = False
        self.logs = []

        class _CTM:
            def __init__(self, config, notify):
                self.config = config
                self.scheduled_file = f"waiting_{config.get('profile_name')}.json"

        self.CopyTradeManager = _CTM

    def notify(self, msg):
        pass

    def log(self, msg):
        self.logs.append(msg)

    def update_scheduled_list_ui(self):
        pass

    def update_ui_state(self, name):
        self._last_ui = name

    def refresh_profile_list(self):
        pass

    def _update_active_profile_badge(self, name):
        self._badge = name


class TestSelectProfile(unittest.TestCase):
    def test_atomic_switch_updates_config_and_copy_manager(self):
        app = FakeApp()
        ok = app.select_profile("B", source="test", clear_console=False)
        self.assertTrue(ok)
        self.assertEqual(app.selected_profile_name, "B")
        self.assertEqual(app.config.get("profile_name"), "B")
        self.assertEqual(app.config.get("path"), "/b")
        self.assertIsNotNone(app.copy_manager)
        self.assertEqual(app.copy_manager.config.get("path"), "/b")
        self.assertIn("waiting_B", app.copy_manager.scheduled_file)

    def test_unknown_profile_noop(self):
        app = FakeApp()
        app.select_profile("A", source="test", clear_console=False)
        ok = app.select_profile("NOPE", source="test", clear_console=False)
        self.assertFalse(ok)
        self.assertEqual(app.selected_profile_name, "A")


if __name__ == "__main__":
    unittest.main()
