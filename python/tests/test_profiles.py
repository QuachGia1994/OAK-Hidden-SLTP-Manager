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
    add_profile,
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


class TestPhase6Settings(unittest.TestCase):
    """Phase 6 — settings get/update (whitelisted) + services list."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="oak-phase6-")
        base = Path(self._tmpdir.name)
        self.settings_file = base / "settings.json"
        self.settings_file.write_text(json.dumps({
            "lang": "VN", "theme": "dark", "ghost_mode_active": True,
            "ntfy_topic": "secret_topic_xyz", "stock_client_id": "oak-scanner",
        }), encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _patch_settings_path(self):
        return patch("oak_core.supervisor.settings._settings_path",
                     return_value=self.settings_file)

    def _patch_data_root(self):
        return patch("oak_core.supervisor.profiles._data_root",
                     return_value=Path(self._tmpdir.name))

    def test_settings_get_masks_secret_topic(self):
        from oak_core.supervisor.settings import public_settings
        with self._patch_settings_path():
            result = public_settings()
        self.assertEqual(result["lang"], "VN")
        self.assertEqual(result["theme"], "dark")
        # ntfy_topic is a presence flag, never the value.
        self.assertTrue(result["ntfy_topic"])
        blob = json.dumps(result)
        self.assertNotIn("secret_topic_xyz", blob)

    def test_settings_update_whitelisted(self):
        from oak_core.supervisor.settings import update_settings
        with self._patch_settings_path():
            result = update_settings({"lang": "EN", "ntfy_topic": "LEAKED", "hack": 1})
        self.assertEqual(result["lang"], "EN")
        blob = json.dumps(result)
        self.assertNotIn("LEAKED", blob)
        self.assertNotIn("hack", blob)

    def test_services_list(self):
        from oak_core.supervisor.settings import services_list
        with self._patch_settings_path(), self._patch_data_root():
            services = services_list()
        keys = [s["key"] for s in services]
        self.assertIn("telegram", keys)
        self.assertIn("screener", keys)
        self.assertIn("signal_bot", keys)
        telegram = next(s for s in services if s["key"] == "telegram")
        self.assertTrue(telegram["configured"])


class TestAddProfile(unittest.TestCase):
    """Tests for the add_profile function."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="oak-addprof-")
        # Start with empty profiles.json
        make_profiles_file(self._tmpdir.name, {})

    def tearDown(self):
        self._tmpdir.cleanup()

    def _patch_data_root(self):
        return patch("oak_core.supervisor.profiles._data_root",
                     return_value=Path(self._tmpdir.name))

    def test_add_profile_creates_and_persists(self):
        with self._patch_data_root():
            result = add_profile("NewBroker", path="C:/mt5/terminal64.exe", magic=88001)
        self.assertEqual(result["profile_name"], "NewBroker")
        self.assertEqual(result["path"], "C:/mt5/terminal64.exe")
        self.assertEqual(result["magic"], 88001)
        self.assertEqual(result["status"], "stopped")
        self.assertIsNone(result["pid"])
        self.assertTrue(result["exists"])
        # Sensitive fields not present
        self.assertNotIn("tele_token", result)
        self.assertNotIn("password", result)
        # Persisted to disk
        with self._patch_data_root():
            disk = load_profiles()
        self.assertIn("NewBroker", disk)
        self.assertEqual(disk["NewBroker"]["path"], "C:/mt5/terminal64.exe")
        self.assertEqual(disk["NewBroker"]["magic"], 88001)
        # No sensitive keys in the stored config either
        self.assertNotIn("tele_token", disk["NewBroker"])

    def test_add_profile_requires_name(self):
        with self._patch_data_root():
            with self.assertRaises(ValueError):
                add_profile("  ")

    def test_add_profile_duplicate_raises(self):
        with self._patch_data_root():
            add_profile("Vantage", path="C:/mt5/terminal64.exe")
            with self.assertRaises(ValueError):
                add_profile("Vantage")


class TestStartProfileFrozenMode(unittest.TestCase):
    """Tests for start_profile in frozen vs dev mode."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="oak-frozen-")
        self.profiles_file = make_profiles_file(self._tmpdir.name, {
            "Vantage": {"path": "C:/mt5/terminal64.exe", "server": "Vantage-Server", "login_id": 1},
        })

    def tearDown(self):
        self._tmpdir.cleanup()

    def _patch_profiles(self):
        return patch("oak_core.supervisor.profiles.profiles_path",
                     return_value=Path(self.profiles_file))

    def test_start_profile_frozen_uses_worker_subcommand(self):
        mgr = ProfileManager(python_executable=sys.executable)
        fake_proc = type("FakeProc", (), {"pid": 123, "poll": lambda self: None,
                                           "stderr": iter([])})()
        with self._patch_profiles(), \
             patch("oak_core.supervisor.profiles.subprocess.Popen", return_value=fake_proc) as fake_popen, \
             patch.object(sys, "frozen", True, create=True):
            result = mgr.start_profile("Vantage")
        self.assertTrue(result["started"])
        self.assertEqual(result["pid"], 123)
        cmd = fake_popen.call_args.args[0]
        self.assertEqual(cmd[1], "profile-worker")
        self.assertIn("Vantage", cmd)
        self.assertIsNone(fake_popen.call_args.kwargs.get("cwd"))

    def test_start_profile_dev_mode_uses_m_flag(self):
        mgr = ProfileManager(python_executable=sys.executable)
        fake_proc = type("FakeProc", (), {"pid": 456, "poll": lambda self: None,
                                           "stderr": iter([])})()
        with self._patch_profiles(), \
             patch("oak_core.supervisor.profiles.subprocess.Popen", return_value=fake_proc) as fake_popen, \
             patch.object(sys, "frozen", False, create=True):
            result = mgr.start_profile("Vantage")
        self.assertTrue(result["started"])
        cmd = fake_popen.call_args.args[0]
        self.assertEqual(cmd[1:3], ["-m", "oak_core"])
        cwd = fake_popen.call_args.kwargs.get("cwd")
        self.assertIsNotNone(cwd)
        self.assertTrue(cwd.endswith("python"))


class TestWorkerLoadProfileDataRoot(unittest.TestCase):
    """Tests for worker._load_profile honoring OAK_DATA_DIR."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="oak-worker-")
        # profiles.json with Vantage
        make_profiles_file(self._tmpdir.name, {
            "Vantage": {"path": "C:/mt5/terminal64.exe", "login_id": 1},
        })

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_worker_load_profile_uses_data_root(self):
        from oak_core.worker import _load_profile
        with patch.dict(os.environ, {"OAK_DATA_DIR": self._tmpdir.name}):
            result = _load_profile("Vantage")
        self.assertEqual(result["path"], "C:/mt5/terminal64.exe")
        self.assertEqual(result["login_id"], 1)

    def test_worker_load_profile_empty_dir_returns_empty(self):
        from oak_core.worker import _load_profile
        with tempfile.TemporaryDirectory(prefix="oak-empty-") as empty:
            with patch.dict(os.environ, {"OAK_DATA_DIR": empty}):
                result = _load_profile("Vantage")
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
