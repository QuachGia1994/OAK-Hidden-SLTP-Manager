# -*- coding: utf-8 -*-
"""Tests for Phase 2 profile supervision (§9) — list/start/stop/status.

The ProfileManager spawns real subprocesses only when a profile actually
exists; tests use a temp profiles.json + a fake python to avoid touching MT5.
"""
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

_python_root = Path(__file__).resolve().parents[1]
if str(_python_root) not in sys.path:
    sys.path.insert(0, str(_python_root))

from oak_core.supervisor.profiles import (  # noqa: E402
    ProfileManager,
    load_profiles,
    public_profile,
    read_sltp,
    read_copy,
    update_sltp,
    update_copy,
)
from oak_core.supervisor import SupervisorApp  # noqa: E402
from oak_core.ipc.server import IpcServer  # noqa: E402


def make_profiles_file(tmpdir: str, profiles: dict) -> str:
    path = Path(tmpdir) / "profiles.json"
    path.write_text(json.dumps(profiles), encoding="utf-8")
    return str(path)


class TestPublicProfile(unittest.TestCase):
    def test_sensitive_fields_never_leak(self):
        cfg = {
            "path": "C:/mt5/terminal64.exe",
            "login_id": 123,
            "server": "Vantage-Server",
            "tele_token": "SECRET_TOKEN",
            "tele_chat": "SECRET_CHAT",
            "password": "SECRET_PW",
            "visible_sltp": True,
        }
        public = public_profile("Vantage", cfg)
        blob = json.dumps(public)
        self.assertNotIn("SECRET", blob)
        self.assertNotIn("tele_token", blob)
        self.assertNotIn("password", blob)
        self.assertIn("path", public)
        self.assertEqual(public["profile_name"], "Vantage")
        self.assertTrue(public["exists"])

    def test_public_profile_missing_config(self):
        public = public_profile("Ghost", {})
        self.assertFalse(public["exists"])


class TestProfileManager(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="oak-profiles-")
        self.profiles_file = make_profiles_file(self._tmpdir.name, {
            "Vantage": {"path": "C:/mt5/terminal64.exe", "server": "Vantage-Server", "login_id": 1},
            "Demo": {"path": "C:/mt5/demo64.exe", "server": "Demo-Server", "login_id": 2},
        })

    def tearDown(self):
        self._tmpdir.cleanup()

    def _manager(self):
        mgr = ProfileManager(python_executable=sys.executable)
        return mgr

    def test_list_profiles_masks_sensitive(self):
        mgr = self._manager()
        with patch("oak_core.supervisor.profiles.profiles_path",
                   return_value=Path(self.profiles_file)):
            result = mgr.list_profiles()
        names = [p["profile_name"] for p in result["profiles"]]
        self.assertEqual(names, ["Vantage", "Demo"])
        for p in result["profiles"]:
            self.assertEqual(p["status"], "stopped")
            self.assertNotIn("login_id", p)

    def test_start_profile_spawns_worker(self):
        mgr = self._manager()
        with patch("oak_core.supervisor.profiles.profiles_path",
                   return_value=Path(self.profiles_file)), \
             patch("oak_core.supervisor.profiles.subprocess.Popen") as fake_popen:
            fake_proc = fake_popen.return_value
            fake_proc.pid = 4242
            fake_proc.poll.return_value = None
            result = mgr.start_profile("Vantage")
        self.assertTrue(result["started"])
        self.assertEqual(result["pid"], 4242)
        # Worker command uses profile-worker mode with the profile name.
        cmd = fake_popen.call_args.args[0]
        self.assertIn("profile-worker", cmd)
        self.assertIn("Vantage", cmd)
        # Same profile not started twice.
        with patch("oak_core.supervisor.profiles.profiles_path",
                   return_value=Path(self.profiles_file)):
            again = mgr.start_profile("Vantage")
        self.assertFalse(again["started"])

    def test_start_unknown_profile_raises(self):
        mgr = self._manager()
        with patch("oak_core.supervisor.profiles.profiles_path",
                   return_value=Path(self.profiles_file)):
            with self.assertRaises(KeyError):
                mgr.start_profile("Ghost")

    def test_status_running_and_stopped(self):
        mgr = self._manager()
        with patch("oak_core.supervisor.profiles.profiles_path",
                   return_value=Path(self.profiles_file)):
            stopped = mgr.profile_status("Demo")
        self.assertEqual(stopped["status"], "stopped")
        self.assertIsNone(stopped["pid"])

        with patch("oak_core.supervisor.profiles.profiles_path",
                   return_value=Path(self.profiles_file)), \
             patch("oak_core.supervisor.profiles.subprocess.Popen") as fake_popen:
            fake_proc = fake_popen.return_value
            fake_proc.pid = 7
            fake_proc.poll.return_value = None
            mgr.start_profile("Demo")
            running = mgr.profile_status("Demo")
        self.assertEqual(running["status"], "running")
        self.assertEqual(running["pid"], 7)

    def test_stop_profile_terminates(self):
        mgr = self._manager()
        with patch("oak_core.supervisor.profiles.profiles_path",
                   return_value=Path(self.profiles_file)), \
             patch("oak_core.supervisor.profiles.subprocess.Popen") as fake_popen:
            fake_proc = fake_popen.return_value
            fake_proc.pid = 9
            fake_proc.poll.return_value = None
            mgr.start_profile("Demo")
            result = mgr.stop_profile("Demo")
        self.assertTrue(result["stopped"])
        fake_proc.terminate.assert_called_once()

    def test_stop_not_running(self):
        mgr = self._manager()
        result = mgr.stop_profile("Vantage")
        self.assertFalse(result["stopped"])
        self.assertEqual(result["reason"], "not running")


class TestPhase5SltpCopy(unittest.TestCase):
    """Phase 5 — hidden SL/TP + copy trading config read/update."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="oak-phase5-")
        self.profiles_file = make_profiles_file(self._tmpdir.name, {
            "Vantage": {
                "path": "C:/mt5/terminal64.exe", "visible_sltp": True,
                "sl": 500, "tp": 10000, "gold_sl": 1000, "gold_tp": 20000,
                "copy_role": "None", "copy_channel": "copy",
                "tele_token": "SECRET",
            },
        })

    def tearDown(self):
        self._tmpdir.cleanup()

    def _patch(self):
        return patch("oak_core.supervisor.profiles.profiles_path",
                     return_value=Path(self.profiles_file))

    def test_read_sltp_whitelisted(self):
        with self._patch():
            result = read_sltp("Vantage")
        self.assertTrue(result["exists"])
        self.assertEqual(result["sltp"]["sl"], 500)
        self.assertEqual(result["sltp"]["tp"], 10000)
        # Secrets never included.
        blob = json.dumps(result)
        self.assertNotIn("SECRET", blob)
        self.assertNotIn("tele_token", blob)

    def test_update_sltp_ignores_non_whitelisted(self):
        with self._patch():
            result = update_sltp("Vantage", {"sl": 600, "hack_field": 999, "tele_token": "LEAK"})
        self.assertEqual(result["sltp"]["sl"], 600)
        blob = json.dumps(result)
        self.assertNotIn("LEAK", blob)
        self.assertNotIn("hack_field", blob)

    def test_read_copy(self):
        with self._patch():
            result = read_copy("Vantage")
        self.assertEqual(result["copy"]["copy_role"], "None")
        self.assertEqual(result["copy"]["copy_channel"], "copy")

    def test_update_copy(self):
        with self._patch():
            result = update_copy("Vantage", {"copy_role": "FOLLOWER", "copy_channel": "oak-main"})
        self.assertEqual(result["copy"]["copy_role"], "FOLLOWER")
        self.assertEqual(result["copy"]["copy_channel"], "oak-main")
        # Persisted to disk.
        with self._patch():
            disk = load_profiles()
        self.assertEqual(disk["Vantage"]["copy_role"], "FOLLOWER")

    def test_update_unknown_profile_raises(self):
        with self._patch():
            with self.assertRaises(KeyError):
                update_sltp("Ghost", {"sl": 1})


class TestSupervisorProfileHandlers(unittest.TestCase):
    def _make_server(self, input_text, profiles_file):
        stdin = io.StringIO(input_text)
        stdout = io.StringIO()
        stderr = io.StringIO()
        server = IpcServer(stdin=stdin, stdout=stdout, stderr=stderr)
        mgr = ProfileManager(python_executable=sys.executable)
        app = SupervisorApp(server=server, profile_manager=mgr)
        return server, stdout, app

    def _responses(self, stdout):
        return [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]

    def test_profiles_list_handler(self):
        with tempfile.TemporaryDirectory(prefix="oak-ipc-") as tmp:
            profiles_file = make_profiles_file(tmp, {"Vantage": {"path": "x"}})
            with patch("oak_core.supervisor.profiles.profiles_path",
                       return_value=Path(profiles_file)):
                server, stdout, app = self._make_server(
                    '{"v":1,"id":"p1","method":"profiles.list"}\n', profiles_file)
                app.run()
            responses = self._responses(stdout)
            self.assertTrue(responses[0]["ok"])
            self.assertEqual(len(responses[0]["result"]["profiles"]), 1)

    def test_profile_start_unknown_returns_error(self):
        with tempfile.TemporaryDirectory(prefix="oak-ipc-") as tmp:
            profiles_file = make_profiles_file(tmp, {"Vantage": {"path": "x"}})
            with patch("oak_core.supervisor.profiles.profiles_path",
                       return_value=Path(profiles_file)):
                server, stdout, app = self._make_server(
                    '{"v":1,"id":"p2","method":"profile.start","params":{"profile":"Ghost"}}\n',
                    profiles_file)
                app.run()
            responses = self._responses(stdout)
            self.assertFalse(responses[0]["ok"])
            self.assertEqual(responses[0]["error"]["code"], "HANDLER_ERROR")

    def test_profile_start_missing_param_returns_error(self):
        with tempfile.TemporaryDirectory(prefix="oak-ipc-") as tmp:
            profiles_file = make_profiles_file(tmp, {"Vantage": {"path": "x"}})
            with patch("oak_core.supervisor.profiles.profiles_path",
                       return_value=Path(profiles_file)):
                server, stdout, app = self._make_server(
                    '{"v":1,"id":"p3","method":"profile.start"}\n', profiles_file)
                app.run()
            responses = self._responses(stdout)
            self.assertFalse(responses[0]["ok"])

    def test_shutdown_stops_all_workers(self):
        with tempfile.TemporaryDirectory(prefix="oak-ipc-") as tmp:
            profiles_file = make_profiles_file(tmp, {"Vantage": {"path": "x"}})
            server, stdout, app = self._make_server(
                '{"v":1,"id":"s","method":"app.shutdown"}\n', profiles_file)
            with patch("oak_core.supervisor.profiles.subprocess.Popen") as fake_popen, \
                 patch("oak_core.supervisor.profiles.profiles_path",
                       return_value=Path(profiles_file)):
                fake_proc = fake_popen.return_value
                fake_proc.pid = 5
                fake_proc.poll.return_value = None
                app._profiles.start_profile("Vantage")
                app.run()
            responses = self._responses(stdout)
            self.assertTrue(responses[0]["ok"])
            self.assertTrue(responses[0]["result"]["ack"])


if __name__ == "__main__":
    unittest.main()
