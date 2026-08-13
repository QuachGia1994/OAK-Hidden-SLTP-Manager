# -*- coding: utf-8 -*-
"""NativeQt profile startup lifecycle — operation token / stale-callback hardening."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from services.mt5_terminal_service import MT5LaunchResult


class _FakeLabel:
    def __init__(self, text=""):
        self._text = text
        self._props = {}
        self._enabled = True

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


class ProfileStartupLifecycleTests(unittest.TestCase):
    def _shell_stub(self, profiles=None):
        import oak_qt_shell as shell_mod

        shell = object.__new__(shell_mod.NativeShell)
        profiles = profiles or {"Vantage": {"path": "C:/mt5/terminal64.exe"}}
        shell.selected = next(iter(profiles))
        shell.profiles = dict(profiles)
        shell.starting_profiles = set()
        shell.startup_phase = {}
        shell.startup_error = {}
        shell._startup_ops = {}
        shell._startup_op_seq = 0
        shell._is_shut_down = False
        shell.monitor_processes = {}
        shell.rail_profile_status = _FakeLabel("Stopped")
        shell.rail_profile_toggle = _FakeLabel("Start selected")
        shell.console_lines = []
        shell.log = MagicMock()

        def _append(msg):
            shell.console_lines.append(msg)

        shell._append_console_line = _append
        shell._running_profiles = lambda: [
            n
            for n, p in shell.monitor_processes.items()
            if getattr(p, "state", lambda: 0)() != 0
        ]
        for name in (
            "_refresh_profile_controls",
            "_publish_startup_phase",
            "_profile_is_running",
            "_ui_after",
            "_next_startup_op",
            "_is_startup_op_current",
            "_invalidate_startup_op",
            "_finish_terminal_startup",
            "stop_profile",
        ):
            setattr(shell, name, getattr(shell_mod.NativeShell, name).__get__(shell))
        return shell

    @staticmethod
    def _immediate_thread_patch():
        class _ImmediateThread:
            def __init__(self, target=None, name=None, daemon=None, args=(), kwargs=None):
                self._target = target

            def start(self):
                if self._target:
                    self._target()

        return patch("oak_qt_shell.threading.Thread", _ImmediateThread)

    def test_startup_operation_token_created(self):
        import oak_qt_shell as shell_mod

        shell = self._shell_stub()
        ok = MT5LaunchResult(True, "C:/mt5/terminal64.exe", False, None, 1, None, None, "ok")
        with self._immediate_thread_patch(), patch(
            "services.mt5_terminal_service.ensure_mt5_profile_connected", return_value=ok
        ), patch.object(shell_mod.NativeShell, "_launch_worker"):
            shell_mod.NativeShell.start_profile(shell, "Vantage")
        # After successful finish the token is consumed (completion claim).
        self.assertEqual(shell._startup_op_seq, 1)
        self.assertNotIn("Vantage", shell._startup_ops)

    def test_stop_invalidates_startup_token(self):
        shell = self._shell_stub()
        op = shell._next_startup_op("Vantage")
        shell.starting_profiles.add("Vantage")
        shell.startup_phase["Vantage"] = "Opening terminal..."
        shell.stop_profile("Vantage")
        self.assertNotIn("Vantage", shell._startup_ops)
        self.assertNotIn("Vantage", shell.starting_profiles)
        self.assertNotIn("Vantage", shell.startup_phase)
        self.assertFalse(shell._is_startup_op_current("Vantage", op))

    def test_stale_success_does_not_launch_worker(self):
        import oak_qt_shell as shell_mod

        shell = self._shell_stub()
        stale_op = shell._next_startup_op("Vantage")
        shell.starting_profiles.add("Vantage")
        # Simulate Stop invalidating the op.
        shell._invalidate_startup_op("Vantage")
        ok = MT5LaunchResult(True, "C:/mt5/terminal64.exe", False, None, 1, None, None, "ok")
        with patch.object(shell_mod.NativeShell, "_launch_worker") as launch_worker:
            shell._finish_terminal_startup("Vantage", ok, None, stale_op)
        launch_worker.assert_not_called()
        self.assertNotIn("Vantage", shell.starting_profiles)

    def test_stale_failure_does_not_mutate_new_start(self):
        shell = self._shell_stub()
        old_op = shell._next_startup_op("Vantage")
        # New Start takes ownership.
        new_op = shell._next_startup_op("Vantage")
        shell.starting_profiles.add("Vantage")
        shell.startup_phase["Vantage"] = "Checking MT5 terminal..."
        shell._finish_terminal_startup(
            "Vantage", None, RuntimeError("late fail"), old_op
        )
        self.assertEqual(shell._startup_ops.get("Vantage"), new_op)
        self.assertIn("Vantage", shell.starting_profiles)
        self.assertEqual(shell.startup_phase.get("Vantage"), "Checking MT5 terminal...")
        self.assertNotIn("Vantage", shell.startup_error)

    def test_start_stop_start_only_new_generation_launches(self):
        import oak_qt_shell as shell_mod

        shell = self._shell_stub()
        ok = MT5LaunchResult(True, "C:/mt5/terminal64.exe", False, None, 1, None, None, "ok")

        # Hold the first ensure so we can Stop before it finishes.
        first_finish = {}

        def ensure_hold(cfg, status_callback=None, **kw):
            if "held" not in first_finish:
                first_finish["held"] = True

                class _Held:
                    ok = True

                # Do not finish here — caller will invoke finish manually for stale op.
                return _Held()
            return ok

        # Use real Thread capture instead of immediate so we can interleave Stop.
        captured = {}

        class _CaptureThread:
            def __init__(self, target=None, name=None, daemon=None, args=(), kwargs=None):
                captured["target"] = target

            def start(self):
                pass  # deferred

        with patch("oak_qt_shell.threading.Thread", _CaptureThread), patch(
            "services.mt5_terminal_service.ensure_mt5_profile_connected", side_effect=ensure_hold
        ), patch.object(shell_mod.NativeShell, "_launch_worker") as launch_worker:
            shell_mod.NativeShell.start_profile(shell, "Vantage")
            first_op = shell._startup_ops["Vantage"]
            self.assertIn("Vantage", shell.starting_profiles)

            # Stop invalidates generation 1.
            shell.stop_profile("Vantage")
            self.assertNotIn("Vantage", shell._startup_ops)

            # Start generation 2 (immediate finish).
            with self._immediate_thread_patch(), patch(
                "services.mt5_terminal_service.ensure_mt5_profile_connected", return_value=ok
            ):
                shell_mod.NativeShell.start_profile(shell, "Vantage")
            second_op = shell._startup_op_seq
            self.assertNotEqual(first_op, second_op)
            launch_worker.assert_called_once_with("Vantage")

            # Late success from generation 1 must be ignored.
            launch_worker.reset_mock()
            shell._finish_terminal_startup("Vantage", ok, None, first_op)
            launch_worker.assert_not_called()

    def test_stale_status_callback_does_not_update_ui(self):
        shell = self._shell_stub()
        old_op = shell._next_startup_op("Vantage")
        shell.starting_profiles.add("Vantage")
        shell._publish_startup_phase("Vantage", "Opening terminal...", old_op)
        self.assertEqual(shell.startup_phase["Vantage"], "Opening terminal...")

        # Supersede.
        new_op = shell._next_startup_op("Vantage")
        shell.startup_phase["Vantage"] = "Checking MT5 terminal..."
        shell._publish_startup_phase("Vantage", "Waiting for IPC...", old_op)
        self.assertEqual(shell.startup_phase["Vantage"], "Checking MT5 terminal...")
        self.assertTrue(shell._is_startup_op_current("Vantage", new_op))

    def test_valid_generation_updates_status(self):
        shell = self._shell_stub()
        op = shell._next_startup_op("Vantage")
        shell.starting_profiles.add("Vantage")
        shell._publish_startup_phase("Vantage", "Verifying account...", op)
        self.assertEqual(shell.startup_phase["Vantage"], "Verifying account...")
        self.assertTrue(any("Verifying account" in line for line in shell.console_lines))

    def test_profile_a_and_b_startup_tokens_are_isolated(self):
        shell = self._shell_stub(
            {"Alpha": {"path": "C:/a.exe"}, "Beta": {"path": "C:/b.exe"}}
        )
        a = shell._next_startup_op("Alpha")
        b = shell._next_startup_op("Beta")
        self.assertNotEqual(a, b)
        self.assertEqual(shell._startup_ops["Alpha"], a)
        self.assertEqual(shell._startup_ops["Beta"], b)
        shell._invalidate_startup_op("Alpha")
        self.assertNotIn("Alpha", shell._startup_ops)
        self.assertEqual(shell._startup_ops.get("Beta"), b)

    def test_startup_exception_cleans_state(self):
        import oak_qt_shell as shell_mod

        shell = self._shell_stub()

        def boom(cfg, status_callback=None, **kw):
            raise RuntimeError("ensure crashed")

        with self._immediate_thread_patch(), patch(
            "services.mt5_terminal_service.ensure_mt5_profile_connected", side_effect=boom
        ), patch.object(shell_mod.NativeShell, "_launch_worker") as launch_worker:
            shell_mod.NativeShell.start_profile(shell, "Vantage")

        launch_worker.assert_not_called()
        self.assertNotIn("Vantage", shell.starting_profiles)
        self.assertNotIn("Vantage", shell._startup_ops)
        self.assertIn("ensure crashed", shell.startup_error.get("Vantage", ""))

    def test_teardown_ignores_late_callback(self):
        import oak_qt_shell as shell_mod

        shell = self._shell_stub()
        op = shell._next_startup_op("Vantage")
        shell.starting_profiles.add("Vantage")
        shell._is_shut_down = True
        shell._startup_ops.clear()
        shell.starting_profiles.clear()
        ok = MT5LaunchResult(True, "C:/mt5/terminal64.exe", False, None, 1, None, None, "ok")
        with patch.object(shell_mod.NativeShell, "_launch_worker") as launch_worker:
            shell._finish_terminal_startup("Vantage", ok, None, op)
            shell._publish_startup_phase("Vantage", "should not apply", op)
        launch_worker.assert_not_called()
        self.assertNotIn("Vantage", shell.startup_phase)

    def test_duplicate_start_still_blocked(self):
        import oak_qt_shell as shell_mod

        shell = self._shell_stub()
        shell.starting_profiles.add("Vantage")
        shell._startup_ops["Vantage"] = 1
        with self._immediate_thread_patch(), patch(
            "services.mt5_terminal_service.ensure_mt5_profile_connected"
        ) as ensure, patch.object(shell_mod.NativeShell, "_launch_worker") as launch_worker:
            shell_mod.NativeShell.start_profile(shell, "Vantage")
        ensure.assert_not_called()
        launch_worker.assert_not_called()
        self.assertEqual(shell._startup_op_seq, 0)

    def test_success_launches_exactly_one_worker(self):
        import oak_qt_shell as shell_mod

        shell = self._shell_stub()
        ok = MT5LaunchResult(True, "C:/mt5/terminal64.exe", False, None, 1, None, None, "ok")
        with self._immediate_thread_patch(), patch(
            "services.mt5_terminal_service.ensure_mt5_profile_connected", return_value=ok
        ), patch.object(shell_mod.NativeShell, "_launch_worker") as launch_worker:
            shell_mod.NativeShell.start_profile(shell, "Vantage")
        launch_worker.assert_called_once_with("Vantage")
        self.assertNotIn("Vantage", shell._startup_ops)


if __name__ == "__main__":
    unittest.main()
