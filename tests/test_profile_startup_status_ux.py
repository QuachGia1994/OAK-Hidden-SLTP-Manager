# -*- coding: utf-8 -*-
"""NativeQt Start Profile readiness UX — phase status surface."""
from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from services.mt5_terminal_service import MT5LaunchResult


class _FakeLabel:
    def __init__(self, text=""):
        self._text = text
        self._props = {}

    def setText(self, text):
        self._text = text

    def text(self):
        return self._text

    def setProperty(self, key, value):
        self._props[key] = value

    def property(self, key):
        return self._props.get(key)

    def style(self):
        return self

    def unpolish(self, *_a):
        return None

    def polish(self, *_a):
        return None

    def setEnabled(self, value):
        self._enabled = bool(value)


class _FakeToggle(_FakeLabel):
    def __init__(self):
        super().__init__("Start selected")
        self._enabled = True


class ProfileStartupStatusUxTests(unittest.TestCase):
    def _shell_stub(self):
        import oak_qt_shell as shell_mod

        shell = object.__new__(shell_mod.NativeShell)
        shell.selected = "Vantage"
        shell.profiles = {"Vantage": {"path": "C:/mt5/terminal64.exe"}}
        shell.starting_profiles = set()
        shell.startup_phase = {}
        shell.startup_error = {}
        shell.monitor_processes = {}
        shell.rail_profile_status = _FakeLabel("Stopped")
        shell.rail_profile_toggle = _FakeToggle()
        shell.console_lines = []

        def _append(msg):
            shell.console_lines.append(msg)

        shell._append_console_line = _append
        shell._running_profiles = lambda: [
            n for n, p in shell.monitor_processes.items() if getattr(p, "state", lambda: 0)() != 0
        ]
        # Bind real methods
        shell._refresh_profile_controls = shell_mod.NativeShell._refresh_profile_controls.__get__(shell)
        shell._publish_startup_phase = shell_mod.NativeShell._publish_startup_phase.__get__(shell)
        shell._profile_is_running = shell_mod.NativeShell._profile_is_running.__get__(shell)
        return shell

    def test_refresh_shows_phase_while_starting(self):
        shell = self._shell_stub()
        shell.starting_profiles.add("Vantage")
        shell.startup_phase["Vantage"] = "Checking MT5 terminal..."
        shell._refresh_profile_controls()
        self.assertEqual(shell.rail_profile_status.text(), "Checking MT5 terminal...")
        self.assertEqual(shell.rail_profile_status.property("accent"), "amber")
        self.assertFalse(shell.rail_profile_toggle._enabled)

    def test_refresh_shows_failure_code(self):
        shell = self._shell_stub()
        shell.startup_error["Vantage"] = "TERMINAL_PATH_NOT_FOUND"
        shell._refresh_profile_controls()
        self.assertIn("TERMINAL_PATH_NOT_FOUND", shell.rail_profile_status.text())
        self.assertTrue(shell.rail_profile_toggle._enabled)

    def test_publish_phase_updates_rail_and_console(self):
        shell = self._shell_stub()
        shell.starting_profiles.add("Vantage")
        shell._publish_startup_phase("Vantage", "Verifying account...")
        self.assertEqual(shell.startup_phase["Vantage"], "Verifying account...")
        self.assertEqual(shell.rail_profile_status.text(), "Verifying account...")
        self.assertTrue(any("Verifying account" in line for line in shell.console_lines))

    def test_start_profile_fail_closed_surfaces_code(self):
        import oak_qt_shell as shell_mod

        shell = self._shell_stub()
        shell.log = MagicMock()
        fail = MT5LaunchResult(
            False, "", False, None, 1, None, "ACCOUNT_MISMATCH", "login mismatch"
        )
        with patch(
            "services.mt5_terminal_service.ensure_mt5_profile_connected", return_value=fail
        ), patch.object(shell_mod.NativeShell, "_launch_worker") as launch_worker:
            shell_mod.NativeShell.start_profile(shell, "Vantage")

        self.assertNotIn("Vantage", shell.starting_profiles)
        self.assertEqual(shell.startup_error.get("Vantage"), "ACCOUNT_MISMATCH")
        launch_worker.assert_not_called()
        self.assertIn("ACCOUNT_MISMATCH", shell.rail_profile_status.text())

    def test_start_profile_success_launches_worker(self):
        import oak_qt_shell as shell_mod

        shell = self._shell_stub()
        shell.log = MagicMock()
        ok = MT5LaunchResult(True, "C:/mt5/terminal64.exe", False, None, 1, None, None, "Connected")
        phases = []

        def capture_phase(profile, phase):
            phases.append(phase)
            shell.startup_phase[profile] = phase

        shell._publish_startup_phase = capture_phase
        with patch(
            "services.mt5_terminal_service.ensure_mt5_profile_connected", return_value=ok
        ) as ensure, patch.object(shell_mod.NativeShell, "_launch_worker") as launch_worker:
            # ensure must receive status_callback
            def _ensure(cfg, status_callback=None, **kw):
                if status_callback:
                    status_callback("Checking MT5 terminal...")
                    status_callback("MT5 terminal ready")
                return ok

            ensure.side_effect = _ensure
            shell_mod.NativeShell.start_profile(shell, "Vantage")

        launch_worker.assert_called_once_with("Vantage")
        self.assertIn("Checking MT5 terminal...", phases)


if __name__ == "__main__":
    unittest.main()
