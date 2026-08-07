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
import types
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
    update_profile,
    duplicate_profile,
    delete_profile,
    secret_status,
    set_tele_token,
    clear_tele_token,
)
from oak_core.supervisor import SupervisorApp  # noqa: E402
from oak_core.ipc.server import IpcServer  # noqa: E402


def make_profiles_file(tmpdir: str, profiles: dict) -> str:
    path = Path(tmpdir) / "profiles.json"
    path.write_text(json.dumps(profiles), encoding="utf-8")
    return str(path)


def dead_worker(pid: int, exit_code: int):
    """A Popen stand-in whose process has already exited (never a real MT5)."""
    return type("DeadProc", (), {
        "pid": pid,
        "poll": lambda self: exit_code,
        "stderr": iter([]),
    })()


class _StopBeforeServicesImport(Exception):
    """Sentinel raised by the import probe — deliberately NOT an ImportError."""


class _ServicesImportProbe:
    """meta_path finder recording sys.path when ``services`` is first imported."""

    def __init__(self):
        self.sys_path_at_import = None

    def find_spec(self, fullname, path=None, target=None):
        if fullname == "services" or fullname.startswith("services."):
            self.sys_path_at_import = list(sys.path)
            raise _StopBeforeServicesImport(fullname)
        return None


class TestPublicProfile(unittest.TestCase):
    def test_sensitive_fields_never_leak(self):
        cfg = {
            "path": "C:/mt5/terminal64.exe",
            "login_id": 123,
            "server": "Vantage-Server",
            "tele_token": "SECRET_TOKEN",
            "tele_chat": "-1001234567890",
            "tele_admin": "987654321",
            "password": "SECRET_PW",
            "visible_sltp": True,
        }
        public = public_profile("Vantage", cfg)
        blob = json.dumps(public)
        self.assertNotIn("SECRET", blob)
        self.assertNotIn("tele_token", blob)
        self.assertNotIn("password", blob)
        # Chat/admin IDs are routing targets, not credentials — they round-trip.
        self.assertEqual(public["tele_chat"], "-1001234567890")
        self.assertEqual(public["tele_admin"], "987654321")
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

    def test_exited_worker_is_never_listed_as_running(self):
        """A crashed worker must report `exited` + its real exit code."""
        mgr = self._manager()
        with patch("oak_core.supervisor.profiles.profiles_path",
                   return_value=Path(self.profiles_file)), \
             patch("oak_core.supervisor.profiles.subprocess.Popen",
                   return_value=dead_worker(4321, 5)):
            mgr.start_profile("Vantage")
            listed = mgr.list_profiles()["profiles"]
            status = mgr.profile_status("Vantage")
            running = mgr.running_workers()
        vantage = next(p for p in listed if p["profile_name"] == "Vantage")
        self.assertEqual(vantage["status"], "exited")
        self.assertEqual(vantage["exit_code"], 5)
        self.assertEqual(vantage["pid"], 4321)
        # Untracked profiles stay stopped, never "exited".
        demo = next(p for p in listed if p["profile_name"] == "Demo")
        self.assertEqual(demo["status"], "stopped")
        self.assertIsNone(demo["pid"])
        self.assertEqual(status["status"], "exited")
        self.assertEqual(running, [])

    def test_live_worker_is_listed_as_running(self):
        mgr = self._manager()
        with patch("oak_core.supervisor.profiles.profiles_path",
                   return_value=Path(self.profiles_file)), \
             patch("oak_core.supervisor.profiles.subprocess.Popen") as fake_popen:
            fake_proc = fake_popen.return_value
            fake_proc.pid = 77
            fake_proc.poll.return_value = None
            mgr.start_profile("Vantage")
            listed = mgr.list_profiles()["profiles"]
            running = mgr.running_workers()
        vantage = next(p for p in listed if p["profile_name"] == "Vantage")
        self.assertEqual(vantage["status"], "running")
        self.assertEqual(vantage["pid"], 77)
        self.assertIsNone(vantage["exit_code"])
        self.assertEqual(running, ["Vantage"])


class TestPhase5SltpCopy(unittest.TestCase):
    """Phase 5 — hidden SL/TP + copy trading config read/update."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="oak-phase5-")
        self.profiles_file = make_profiles_file(self._tmpdir.name, {
            "Vantage": {
                "path": "C:/mt5/terminal64.exe", "visible_sltp": True,
                "sl": 500, "tp": 10000, "gold_sl": 1000, "gold_tp": 20000,
                "copy_role": "None", "copy_channel": "copy",
                "copy_lot_mode": "fixed", "copy_lot_value": 0.1,
                "tele_token": "SECRET",
            },
            # Legacy profile written before the copy lot fields existed.
            "Legacy": {"path": "C:/mt5/terminal64.exe", "copy_role": "None"},
            # Explicit falsy values must survive the read-side defaulting.
            "ZeroLot": {"copy_lot_mode": "", "copy_lot_value": 0},
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
        # Lot sizing is owned by the dedicated copy page.
        self.assertEqual(result["copy"]["copy_lot_mode"], "fixed")
        self.assertEqual(result["copy"]["copy_lot_value"], 0.1)
        blob = json.dumps(result)
        self.assertNotIn("SECRET", blob)
        self.assertNotIn("tele_token", blob)

    def test_read_copy_defaults_lot_fields_for_legacy_profiles(self):
        """Missing lot fields read back as the domain defaults, never None."""
        with self._patch():
            legacy = read_copy("Legacy")
            zero = read_copy("ZeroLot")
        self.assertEqual(legacy["copy"]["copy_lot_mode"], "Fixed")
        self.assertEqual(legacy["copy"]["copy_lot_value"], "0.01")
        # Other missing copy fields keep their existing None semantics.
        self.assertIsNone(legacy["copy"]["copy_channel"])
        # Explicit falsy values are preserved (no truthiness defaulting).
        self.assertEqual(zero["copy"]["copy_lot_mode"], "")
        self.assertEqual(zero["copy"]["copy_lot_value"], 0)

    def test_update_copy(self):
        with self._patch():
            result = update_copy("Vantage", {
                "copy_role": "FOLLOWER", "copy_channel": "oak-main",
                "copy_lot_mode": "ratio", "copy_lot_value": 0.5,
                "hack_field": 999, "tele_token": "LEAK",
            })
        self.assertEqual(result["copy"]["copy_role"], "FOLLOWER")
        self.assertEqual(result["copy"]["copy_channel"], "oak-main")
        self.assertEqual(result["copy"]["copy_lot_mode"], "ratio")
        self.assertEqual(result["copy"]["copy_lot_value"], 0.5)
        blob = json.dumps(result)
        self.assertNotIn("LEAK", blob)
        self.assertNotIn("hack_field", blob)
        # Persisted to disk.
        with self._patch():
            disk = load_profiles()
        self.assertEqual(disk["Vantage"]["copy_role"], "FOLLOWER")
        self.assertEqual(disk["Vantage"]["copy_lot_mode"], "ratio")
        self.assertEqual(disk["Vantage"]["copy_lot_value"], 0.5)
        self.assertNotIn("hack_field", disk["Vantage"])

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

    def test_health_omits_exited_workers(self):
        with tempfile.TemporaryDirectory(prefix="oak-ipc-") as tmp:
            profiles_file = make_profiles_file(tmp, {"Vantage": {"path": "x"}})
            server, stdout, app = self._make_server(
                '{"v":1,"id":"h1","method":"app.health"}\n', profiles_file)
            with patch("oak_core.supervisor.profiles.subprocess.Popen",
                       return_value=dead_worker(11, 9)), \
                 patch("oak_core.supervisor.profiles.profiles_path",
                       return_value=Path(profiles_file)):
                app._profiles.start_profile("Vantage")
                app.run()
            responses = self._responses(stdout)
            self.assertTrue(responses[0]["ok"])
            self.assertEqual(responses[0]["result"]["workers"], [])

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

    def test_add_profile_magic_string_coerced(self):
        with self._patch_data_root():
            result = add_profile("M7", path="C:/mt5/terminal64.exe", magic="7")
        self.assertEqual(result["magic"], 7)
        with self._patch_data_root():
            disk = load_profiles()
        self.assertIsInstance(disk["M7"]["magic"], int)
        self.assertEqual(disk["M7"]["magic"], 7)


class TestProfileEditorSurface(unittest.TestCase):
    """Full editor operations remain non-secret and atomic."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="oak-editor-")
        self._path = Path(self._tmpdir.name) / "profiles.json"
        self._path.write_text(json.dumps({
            "Vantage": {"path": "C:/mt5/terminal64.exe", "visible_sltp": True,
                         "copy_role": "None", "tele_token": "SECRET"},
        }), encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _patch(self):
        return patch("oak_core.supervisor.profiles.profiles_path", return_value=self._path)

    def test_update_rename_and_mask_secret(self):
        with self._patch():
            result = update_profile("Vantage", {"profile_name": "Vantage Demo", "path": "D:/mt5.exe"})
        self.assertEqual(result["profile_name"], "Vantage Demo")
        self.assertEqual(result["path"], "D:/mt5.exe")
        self.assertNotIn("tele_token", json.dumps(result))
        disk = json.loads(self._path.read_text(encoding="utf-8"))
        self.assertNotIn("Vantage", disk)
        self.assertEqual(disk["Vantage Demo"]["tele_token"], "SECRET")

    def test_sensitive_update_is_rejected(self):
        with self._patch():
            with self.assertRaises(ValueError):
                update_profile("Vantage", {"tele_token": "LEAK"})

    # -- Regression: magic coercion ------------------------------------ #
    def test_update_magic_coerces_string_to_int(self):
        with self._patch():
            result = update_profile("Vantage", {"magic": "123"})
        self.assertEqual(result["magic"], 123)
        disk = json.loads(self._path.read_text(encoding="utf-8"))
        self.assertIsInstance(disk["Vantage"]["magic"], int)
        self.assertEqual(disk["Vantage"]["magic"], 123)

    def test_update_magic_empty_becomes_neg_one(self):
        with self._patch():
            result = update_profile("Vantage", {"magic": ""})
        self.assertEqual(result["magic"], -1)
        disk = json.loads(self._path.read_text(encoding="utf-8"))
        self.assertEqual(disk["Vantage"]["magic"], -1)

    def test_update_magic_invalid_raises(self):
        disk_before = self._path.read_text(encoding="utf-8")
        with self._patch():
            with self.assertRaisesRegex(ValueError, "magic must be an integer"):
                update_profile("Vantage", {"magic": "abc"})
        # profiles.json unchanged
        self.assertEqual(self._path.read_text(encoding="utf-8"), disk_before)

    def test_delete_missing_profile_valueerror(self):
        with self._patch():
            with self.assertRaisesRegex(ValueError, "not found"):
                delete_profile("Ghost")

    def test_update_missing_profile_valueerror(self):
        with self._patch():
            with self.assertRaisesRegex(ValueError, "not found"):
                update_profile("Ghost", {"sl": 1})

    def test_duplicate_and_delete(self):
        with self._patch():
            copy = duplicate_profile("Vantage")
            deleted = delete_profile(copy["profile_name"])
        self.assertTrue(deleted["deleted"])
        self.assertNotEqual(copy["profile_name"], "Vantage")


def fake_secret_store(*, available=True, token="", store_ok=True, delete_ok=True):
    """In-memory stand-in for secret_store — never touches the real keyring."""
    store = types.SimpleNamespace(calls=[], vault={"token": token})

    def _store_secret(profile, key, value):
        store.calls.append(("store", profile, key, value))
        if not store_ok:
            raise RuntimeError("keyring store failed")
        store.vault["token"] = value
        return True

    def _delete_secret(profile, key):
        store.calls.append(("delete", profile, key))
        if not delete_ok:
            return False
        store.vault["token"] = ""
        return True

    store.is_keyring_available = lambda: available
    store.get_token_for_profile = lambda profile: store.vault["token"]
    store.store_secret = _store_secret
    store.delete_secret = _delete_secret
    return store


class TestTelegramRoutingFields(unittest.TestCase):
    """tele_chat/tele_admin are routing IDs (editable); tele_token is not."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="oak-tele-")
        self._path = Path(self._tmpdir.name) / "profiles.json"
        self._path.write_text(json.dumps({
            "Vantage": {"path": "C:/mt5/terminal64.exe", "tele_chat": "-1001",
                        "tele_admin": "7", "tele_token": "__vault__"},
        }), encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _patch(self):
        return patch("oak_core.supervisor.profiles.profiles_path", return_value=self._path)

    def _disk(self):
        return json.loads(self._path.read_text(encoding="utf-8"))

    def test_chat_and_admin_are_listed_and_updatable(self):
        mgr = ProfileManager(python_executable=sys.executable)
        with self._patch():
            listed = mgr.list_profiles()["profiles"][0]
            updated = update_profile("Vantage", {"tele_chat": "-1002", "tele_admin": "9"})
        self.assertEqual(listed["tele_chat"], "-1001")
        self.assertEqual(listed["tele_admin"], "7")
        self.assertNotIn("tele_token", json.dumps(listed))
        self.assertEqual(updated["tele_chat"], "-1002")
        self.assertEqual(updated["tele_admin"], "9")
        self.assertNotIn("tele_token", json.dumps(updated))
        # The vault marker survives an unrelated profile update.
        self.assertEqual(self._disk()["Vantage"]["tele_token"], "__vault__")

    def test_token_update_through_profile_update_is_rejected(self):
        with self._patch():
            with self.assertRaises(ValueError):
                update_profile("Vantage", {"tele_token": "123:LEAK"})
        self.assertEqual(self._disk()["Vantage"]["tele_token"], "__vault__")


class TestTelegramTokenSecrets(unittest.TestCase):
    """Token stays write-only: keyring in, presence flags out."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="oak-tele-secret-")
        self._path = Path(self._tmpdir.name) / "profiles.json"
        self._path.write_text(json.dumps({
            "Vantage": {"path": "C:/mt5/terminal64.exe", "tele_token": "__vault__"},
        }), encoding="utf-8")

    def tearDown(self):
        self._tmpdir.cleanup()

    def _patch(self, store):
        return (
            patch("oak_core.supervisor.profiles.profiles_path", return_value=self._path),
            patch("oak_core.supervisor.profiles._secret_store", return_value=store),
        )

    def _run(self, store, fn, *args):
        paths, secrets = self._patch(store)
        with paths, secrets:
            return fn(*args)

    def _disk(self):
        return json.loads(self._path.read_text(encoding="utf-8"))

    def test_status_reports_flags_only(self):
        store = fake_secret_store(token="123:REALTOKEN")
        result = self._run(store, secret_status, "Vantage")
        self.assertEqual(set(result), {"profile", "tele_token_configured", "keyring_available"})
        self.assertTrue(result["tele_token_configured"])
        self.assertTrue(result["keyring_available"])
        self.assertNotIn("REALTOKEN", json.dumps(result))

    def test_status_unknown_profile_raises(self):
        store = fake_secret_store()
        with self.assertRaisesRegex(ValueError, "not found"):
            self._run(store, secret_status, "Ghost")

    def test_set_token_stores_in_keyring_and_persists_marker_only(self):
        store = fake_secret_store(token="")
        result = self._run(store, set_tele_token, "Vantage", "123:NEWTOKEN")
        self.assertEqual(store.calls, [("store", "Vantage", "tele_token", "123:NEWTOKEN")])
        self.assertEqual(self._disk()["Vantage"]["tele_token"], "__vault__")
        self.assertNotIn("NEWTOKEN", self._path.read_text(encoding="utf-8"))
        self.assertNotIn("NEWTOKEN", json.dumps(result))
        self.assertEqual(set(result), {"profile", "tele_token_configured", "keyring_available"})
        self.assertTrue(result["tele_token_configured"])

    def test_set_token_rejects_empty_masked_and_marker(self):
        store = fake_secret_store(token="")
        for bad in ("", "   ", "••••", "__vault__"):
            with self.assertRaises(ValueError):
                self._run(store, set_tele_token, "Vantage", bad)
        self.assertEqual(store.calls, [])

    def test_set_token_without_keyring_never_writes_plaintext(self):
        store = fake_secret_store(available=False)
        with self.assertRaises(RuntimeError):
            self._run(store, set_tele_token, "Vantage", "123:NEWTOKEN")
        self.assertEqual(store.calls, [])
        self.assertEqual(self._disk()["Vantage"]["tele_token"], "__vault__")
        self.assertNotIn("NEWTOKEN", self._path.read_text(encoding="utf-8"))

    def test_clear_token_success_empties_marker(self):
        store = fake_secret_store(token="123:REALTOKEN")
        result = self._run(store, clear_tele_token, "Vantage")
        self.assertEqual(store.calls, [("delete", "Vantage", "tele_token")])
        self.assertTrue(result["cleared"])
        self.assertFalse(result["tele_token_configured"])
        self.assertEqual(set(result),
                         {"profile", "cleared", "tele_token_configured", "keyring_available"})
        self.assertEqual(self._disk()["Vantage"]["tele_token"], "")

    def test_clear_token_failure_keeps_vault_marker(self):
        store = fake_secret_store(token="123:REALTOKEN", delete_ok=False)
        result = self._run(store, clear_tele_token, "Vantage")
        self.assertFalse(result["cleared"])
        self.assertTrue(result["tele_token_configured"])
        self.assertEqual(self._disk()["Vantage"]["tele_token"], "__vault__")
        self.assertNotIn("REALTOKEN", json.dumps(result))


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


class TestWorkerImportOrder(unittest.TestCase):
    """Regression for the sidecar failure `No module named 'services'`.

    The worker is spawned with cwd=<repo>/python, so the repo root must be on
    sys.path BEFORE ``services.mt5_terminal_service`` is imported.  The probe
    aborts the run at that import, so MetaTrader5 is stubbed and no terminal,
    profile or MT5 connection is ever touched.
    """

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="oak-worker-import-")
        # sys.executable is a real file, so the terminal-path guard passes; it is
        # never launched because the probe stops the run before connecting.
        make_profiles_file(self._tmpdir.name, {
            "Vantage": {"path": sys.executable, "login_id": 1},
        })

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_repo_root_is_on_sys_path_before_services_import(self):
        from oak_core import worker

        repo_root = str(worker._repo_root())
        probe = _ServicesImportProbe()
        saved_path = list(sys.path)
        saved_services = {name: module for name, module in sys.modules.items()
                          if name == "services" or name.startswith("services.")}
        saved_mt5 = sys.modules.get("MetaTrader5")
        try:
            for name in saved_services:
                del sys.modules[name]
            sys.modules["MetaTrader5"] = types.ModuleType("MetaTrader5")
            sys.path[:] = [entry for entry in sys.path if entry != repo_root]
            sys.meta_path.insert(0, probe)
            with patch.dict(os.environ, {"OAK_DATA_DIR": self._tmpdir.name}):
                with self.assertRaises(_StopBeforeServicesImport):
                    worker.run_profile_worker("Vantage", once=True)
        finally:
            sys.meta_path.remove(probe)
            sys.path[:] = saved_path
            if saved_mt5 is None:
                sys.modules.pop("MetaTrader5", None)
            else:
                sys.modules["MetaTrader5"] = saved_mt5
            sys.modules.update(saved_services)

        self.assertIsNotNone(probe.sys_path_at_import,
                             "worker never reached the services import")
        self.assertIn(repo_root, probe.sys_path_at_import)


if __name__ == "__main__":
    unittest.main()
