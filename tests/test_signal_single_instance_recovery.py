# -*- coding: utf-8 -*-
"""Focused tests for Signal tab single-instance recovery."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.signal_process_supervisor import (
    SignalProcessSupervisor,
    is_duplicate_instance_line,
    parse_duplicate_instance_pid,
    read_lock_file_pid,
    validate_conflicting_pid,
)


class TestParseDuplicateMessages(unittest.TestCase):
    def test_parse_duplicate_line_with_pid(self):
        line = "  [EXIT] mimo_bot already running (PID 12345). Avoid Telegram 409 Conflict."
        self.assertTrue(is_duplicate_instance_line(line))
        self.assertEqual(parse_duplicate_instance_pid(line), 12345)

    def test_parse_mimo_worker_english_contract(self):
        line = "[WARN] MiMo Worker already running (PID 4242)"
        self.assertTrue(is_duplicate_instance_line(line))
        self.assertEqual(parse_duplicate_instance_pid(line), 4242)

    def test_duplicate_line_without_pid(self):
        line = "[WARN] MiMo Worker dang chay roi. Bo qua."
        self.assertTrue(is_duplicate_instance_line(line))
        self.assertIsNone(parse_duplicate_instance_pid(line))

    def test_non_duplicate_line(self):
        line = "Signal started OK"
        self.assertFalse(is_duplicate_instance_line(line))
        self.assertIsNone(parse_duplicate_instance_pid(line))


class TestLockFilePid(unittest.TestCase):
    def test_read_lock_file_pid(self):
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "mimo_worker.lock"
            lock.write_text("7788", encoding="utf-8")
            self.assertEqual(read_lock_file_pid("mimo_worker", root_dir=tmp), 7788)

    def test_read_lock_file_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(read_lock_file_pid("mimo_worker", root_dir=tmp))


class TestValidateConflictingPid(unittest.TestCase):
    def test_invalid_pid(self):
        verdict, _ = validate_conflicting_pid("mimo_bot", 0)
        self.assertEqual(verdict, "mismatch")

    def test_supervisor_self_pid(self):
        verdict, detail = validate_conflicting_pid("mimo_bot", os.getpid())
        self.assertEqual(verdict, "mismatch")
        self.assertIn("supervisor", detail)

    def test_current_managed_proc_pid(self):
        verdict, detail = validate_conflicting_pid(
            "mimo_bot", 999001, current_proc_pid=999001
        )
        self.assertEqual(verdict, "mismatch")
        self.assertIn("current managed", detail)

    def test_pid_gone(self):
        with patch(
            "services.signal_process_supervisor._psutil_probe",
            return_value=(False, None),
        ):
            verdict, _ = validate_conflicting_pid("mimo_bot", 555001)
        self.assertEqual(verdict, "gone")

    def test_wrong_process_identity(self):
        with patch(
            "services.signal_process_supervisor._psutil_probe",
            return_value=(True, "python.exe notepad.exe"),
        ):
            verdict, _ = validate_conflicting_pid(
                "mimo_bot",
                555002,
                script_map={"mimo_bot": "mimo_bot.py"},
                frozen_flags={"mimo_bot": "--mimo-bot"},
            )
        self.assertEqual(verdict, "mismatch")

    def test_matching_process_identity(self):
        with patch(
            "services.signal_process_supervisor._psutil_probe",
            return_value=(True, r"c:\python\python.exe -u mimo_bot.py"),
        ):
            verdict, _ = validate_conflicting_pid(
                "mimo_bot",
                555003,
                script_map={"mimo_bot": "mimo_bot.py"},
                frozen_flags={"mimo_bot": "--mimo-bot"},
            )
        self.assertEqual(verdict, "matches")

    def test_unknown_when_metadata_missing(self):
        with patch(
            "services.signal_process_supervisor._psutil_probe",
            return_value=(None, None),
        ), patch(
            "services.signal_process_supervisor._tasklist_alive",
            return_value=True,
        ), patch(
            "services.signal_process_supervisor._powershell_cmdline",
            return_value=None,
        ):
            verdict, _ = validate_conflicting_pid("mimo_bot", 555004)
        self.assertEqual(verdict, "unknown")


class TestOrphanReconciliation(unittest.TestCase):
    def _make_supervisor(self):
        sup = SignalProcessSupervisor(signal_defs=[])
        sup.ui_after = lambda fn: fn()
        return sup

    def test_live_locked_instance_is_never_force_killed(self):
        sup = self._make_supervisor()
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "mimo_worker.lock"
            lock.write_text("4242", encoding="utf-8")
            with patch(
                "services.signal_process_supervisor.os.path.dirname",
                side_effect=[tmp, tmp],
            ):
                with patch(
                    "services.signal_process_supervisor.read_lock_file_pid",
                    return_value=4242,
                ), patch(
                    "services.signal_process_supervisor.validate_conflicting_pid",
                    return_value=("matches", "managed process is alive"),
                ), patch(
                    "services.signal_process_supervisor.terminate_pid"
                ) as terminate:
                    sup._kill_orphan_processes("mimo_worker")
            terminate.assert_not_called()
            self.assertTrue(lock.exists())

    def test_dead_locked_instance_is_reconciled(self):
        sup = self._make_supervisor()
        with tempfile.TemporaryDirectory() as tmp:
            lock = Path(tmp) / "mimo_worker.lock"
            lock.write_text("4242", encoding="utf-8")
            with patch(
                "services.signal_process_supervisor.read_lock_file_pid",
                return_value=4242,
            ), patch(
                "services.signal_process_supervisor.validate_conflicting_pid",
                return_value=("gone", "process no longer exists"),
            ), patch(
                "services.signal_process_supervisor.os.path.dirname",
                return_value=tmp,
            ):
                sup._kill_orphan_processes("mimo_worker")
            self.assertFalse(lock.exists())


class TestRecoveryDecisions(unittest.TestCase):
    def _make_supervisor(self):
        sup = SignalProcessSupervisor(signal_defs=[])
        # Run UI callbacks inline for deterministic tests.
        sup.ui_after = lambda fn: fn()
        sup._signal_procs = {
            "mimo_bot": {
                "name": "MiMo Telegram Bot",
                "proc": None,
                "logs": [],
                "lbl_pid": None,
                "btn_start": None,
                "btn_stop": None,
                "lbl_status": None,
                "console": None,
            }
        }
        return sup

    def test_matching_pid_terminates_and_restarts_once(self):
        sup = self._make_supervisor()
        proc = MagicMock()
        proc.pid = 1001
        proc.poll.return_value = 1
        sup._signal_procs["mimo_bot"]["proc"] = proc
        sup._last_profile["mimo_bot"] = "VantageDemo"

        with patch(
            "services.signal_process_supervisor.validate_conflicting_pid",
            return_value=("matches", "ok"),
        ), patch(
            "services.signal_process_supervisor.terminate_pid"
        ) as term, patch.object(
            sup, "start_signal_process"
        ) as start:
            owned = sup._try_duplicate_recovery(
                "mimo_bot",
                proc,
                "[EXIT] mimo_bot already running (PID 4242)",
            )

        self.assertTrue(owned)
        term.assert_called_once_with(4242)
        start.assert_called_once_with("mimo_bot", "VantageDemo", _recovery=True)
        self.assertTrue(sup._auto_restart_attempted["mimo_bot"])

    def test_second_duplicate_does_not_restart(self):
        sup = self._make_supervisor()
        proc = MagicMock()
        proc.pid = 1002
        sup._signal_procs["mimo_bot"]["proc"] = proc
        sup._auto_restart_attempted["mimo_bot"] = True

        with patch(
            "services.signal_process_supervisor.validate_conflicting_pid",
            return_value=("matches", "ok"),
        ), patch(
            "services.signal_process_supervisor.terminate_pid"
        ) as term, patch.object(
            sup, "start_signal_process"
        ) as start, patch.object(
            sup, "_set_running_ui"
        ) as set_ui:
            owned = sup._try_duplicate_recovery(
                "mimo_bot",
                proc,
                "[EXIT] mimo_bot already running (PID 4242)",
            )

        self.assertTrue(owned)
        term.assert_not_called()
        start.assert_not_called()
        set_ui.assert_called()
        kwargs = set_ui.call_args.kwargs
        self.assertEqual(kwargs.get("conflict_pid"), 4242)

    def test_explicit_stop_skips_recovery(self):
        sup = self._make_supervisor()
        proc = MagicMock()
        proc.pid = 1003
        sup._intentional_stop["mimo_bot"] = True

        with patch(
            "services.signal_process_supervisor.terminate_pid"
        ) as term, patch.object(sup, "start_signal_process") as start:
            owned = sup._try_duplicate_recovery(
                "mimo_bot",
                proc,
                "[EXIT] mimo_bot already running (PID 4242)",
            )

        self.assertFalse(owned)
        term.assert_not_called()
        start.assert_not_called()

    def test_unsafe_pid_shows_conflict_no_kill(self):
        sup = self._make_supervisor()
        proc = MagicMock()
        proc.pid = 1004
        sup._signal_procs["mimo_bot"]["proc"] = proc

        with patch(
            "services.signal_process_supervisor.validate_conflicting_pid",
            return_value=("unknown", "metadata unavailable"),
        ), patch(
            "services.signal_process_supervisor.terminate_pid"
        ) as term, patch.object(
            sup, "start_signal_process"
        ) as start, patch.object(
            sup, "_set_running_ui"
        ) as set_ui:
            owned = sup._try_duplicate_recovery(
                "mimo_bot",
                proc,
                "[EXIT] mimo_bot already running (PID 7777)",
            )

        self.assertTrue(owned)
        term.assert_not_called()
        start.assert_not_called()
        self.assertEqual(set_ui.call_args.kwargs.get("conflict_pid"), 7777)

    def test_gone_pid_restarts_once_without_terminate(self):
        sup = self._make_supervisor()
        proc = MagicMock()
        proc.pid = 1005
        sup._signal_procs["mimo_bot"]["proc"] = proc

        with patch(
            "services.signal_process_supervisor.validate_conflicting_pid",
            return_value=("gone", "process no longer exists"),
        ), patch(
            "services.signal_process_supervisor.terminate_pid"
        ) as term, patch.object(
            sup, "start_signal_process"
        ) as start:
            owned = sup._try_duplicate_recovery(
                "mimo_bot",
                proc,
                "[EXIT] mimo_bot already running (PID 8888)",
            )

        self.assertTrue(owned)
        term.assert_not_called()
        start.assert_called_once_with("mimo_bot", "", _recovery=True)

    def test_user_start_resets_recovery_budget(self):
        sup = self._make_supervisor()
        sup._auto_restart_attempted["mimo_bot"] = True
        # Avoid real Popen; force early return after budget reset by faking live proc.
        live = MagicMock()
        live.poll.return_value = None
        sup._signal_procs["mimo_bot"]["proc"] = live
        sup.start_signal_process("mimo_bot", "ProfA")
        # Early return because already running, but budget must still reset for user start.
        # Actually early return happens BEFORE budget reset in our code if proc alive...
        # Re-check implementation: budget reset is after early return check.
        # So for truly dead proc path:
        sup._signal_procs["mimo_bot"]["proc"] = None
        sup._auto_restart_attempted["mimo_bot"] = True

        with patch.object(sup, "_kill_orphan_processes"), patch(
            "services.signal_process_supervisor.subprocess.Popen"
        ) as popen, patch(
            "services.signal_process_supervisor.threading.Thread"
        ):
            mock_proc = MagicMock()
            mock_proc.pid = 3210
            mock_proc.poll.return_value = None
            popen.return_value = mock_proc
            with patch(
                "utils.build_signal_process_cmd", return_value=["python", "-u", "mimo_bot.py"]
            ):
                sup.start_signal_process("mimo_bot", "ProfA")

        self.assertFalse(sup._auto_restart_attempted.get("mimo_bot", True))
        self.assertEqual(sup._last_profile.get("mimo_bot"), "ProfA")


if __name__ == "__main__":
    unittest.main()
