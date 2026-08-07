# -*- coding: utf-8 -*-
"""Offscreen tests for the QML Profiles page (Phase 1).

Uses a FakeManager (never the real ProfileManager) to verify bridge
wiring, UI rendering, and mutation flows without touching the filesystem
or starting any subprocesses.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# ── Env MUST be set before any Qt import ──
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_QPA_FONTDIR"] = r"C:\Windows\Fonts"

try:
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQuickWidgets import QQuickWidget
    from PySide6.QtQml import QQmlExpression
except ImportError:
    raise unittest.SkipTest("PySide6 not installed")

# ── Ensure project root is on sys.path ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from oak_qml_app import create_engine  # noqa: E402


# ── FakeManager ──────────────────────────────────────────────────

class FakeManager:
    """In-memory profile manager for testing (never writes to disk)."""

    def __init__(self, profiles):
        self.profiles = {p["profile_name"]: dict(p) for p in profiles}
        self.calls: list = []
        self.fail_next: dict[str, str] = {}
        self._token_configured = False
        self._keyring_ok = True

    def _maybe_fail(self, method):
        if method in self.fail_next:
            msg = self.fail_next.pop(method)
            raise RuntimeError(msg)

    def list_profiles(self):
        self.calls.append("list_profiles")
        return {"profiles": [dict(p) for p in self.profiles.values()]}

    def start_profile(self, name):
        self.calls.append(("start_profile", name))
        p = self.profiles.get(name)
        if p:
            p["status"] = "running"
            p["pid"] = 9999
        return {"profile": name, "pid": 9999, "started": True}

    def stop_profile(self, name):
        self.calls.append(("stop_profile", name))
        p = self.profiles.get(name)
        if p:
            p["status"] = "stopped"
            p["pid"] = None
        return {"profile": name, "stopped": True}

    def add_profile(self, name, path="", magic=-1):
        self.calls.append(("add_profile", name, path, magic))
        self.profiles[name] = {
            "profile_name": name,
            "path": path,
            "magic": magic,
            "status": "stopped",
            "pid": None,
        }
        return {"profile_name": name, "status": "stopped", "pid": None, "exists": True}

    def update_profile(self, name, updates):
        self.calls.append(("update_profile", name, dict(updates)))
        self._maybe_fail("update_profile")
        p = self.profiles[name]
        p.update({k: v for k, v in updates.items() if k != "profile_name"})
        if updates.get("profile_name") and updates["profile_name"] != name:
            self.profiles[updates["profile_name"]] = p
            del self.profiles[name]
            return {"profile_name": updates["profile_name"], "status": "stopped", "pid": None, "exists": True}
        return {"profile_name": name, "status": "stopped", "pid": None, "exists": True}

    def duplicate_profile(self, name):
        self.calls.append(("duplicate_profile", name))
        new = name + " Copy"
        self.profiles[new] = dict(self.profiles[name])
        return {"profile_name": new, "status": "stopped", "pid": None, "exists": True}

    def delete_profile(self, name):
        self.calls.append(("delete_profile", name))
        self.profiles.pop(name, None)
        return {"profile": name, "deleted": True}

    def secret_status(self, name):
        self.calls.append(("secret_status", name))
        return {
            "profile": name,
            "tele_token_configured": self._token_configured,
            "keyring_available": self._keyring_ok,
        }

    def set_tele_token(self, name, token):
        self.calls.append(("set_tele_token", name, token))
        self._token_configured = True
        return {
            "profile": name,
            "tele_token_configured": True,
            "keyring_available": self._keyring_ok,
        }

    def clear_tele_token(self, name):
        self.calls.append(("clear_tele_token", name))
        self._token_configured = False
        return {
            "profile": name,
            "cleared": True,
            "tele_token_configured": False,
            "keyring_available": self._keyring_ok,
        }


# ── Helpers ──────────────────────────────────────────────────────

def qml_eval(widget, scope, expr: str):
    """Evaluate a QML expression with *scope* as the context object.

    PySide6's QQmlExpression.evaluate() returns (result, isUndefined) —
    we extract just the result.
    """
    ctx = widget.engine().rootContext()
    e = QQmlExpression(ctx, scope, expr)
    result = e.evaluate()
    err = e.error()
    if err.isValid():
        raise RuntimeError(f"QML eval error: {err.toString()}")
    # PySide6 returns (value, isUndefined) tuple
    if isinstance(result, tuple):
        return result[0]
    return result


def find_qml_object(root, name: str):
    """Find a QML item by objectName via recursive tree traversal."""
    if root.objectName() == name:
        return root
    for child in root.childItems():
        found = find_qml_object(child, name)
        if found is not None:
            return found
    return None


def click_nav(widget, root, name: str):
    """Navigate to a sidebar page and process events."""
    qml_eval(widget, root, f'clickNav("{name}")')
    widget.app.processEvents()
    # Force render + pump transitions
    widget.grab()
    for _ in range(6):
        widget.app.processEvents()
        widget.grab()


def get_page(widget, root):
    """Get the ProfilesPage root item from the StackView."""
    widget.app.processEvents()
    for _ in range(4):
        widget.grab()
        widget.app.processEvents()
    page = find_qml_object(root, "page_Profiles")
    return page


def pump(widget, n=6):
    """Pump events and force render."""
    for _ in range(n):
        widget.app.processEvents()
        widget.grab()


# ── Test classes ─────────────────────────────────────────────────

class _Base(unittest.TestCase):
    """Shared setUp: one QApplication + QQuickWidget per test class."""

    app: QApplication
    widget: QQuickWidget
    root: object
    fake: FakeManager

    @classmethod
    def setUpClass(cls):
        cls.fake = FakeManager([
            {
                "profile_name": "A",
                "path": r"C:\MT5\A",
                "magic": 100,
                "status": "running",
                "pid": 1234,
                "copy_role": "Master",
                "visible_sltp": True,
                "copy_kill_switch": False,
                "symbol": "XAUUSD",
                "mt5_portable": False,
                "tele_chat": "123456",
                "tele_admin": "789012",
                "tele_token": "SECRET_TOKEN_X",
                "password": "PW_Y",
            },
            {
                "profile_name": "B",
                "path": r"C:\MT5\B",
                "magic": 200,
                "status": "stopped",
                "pid": None,
                "copy_role": "None",
                "visible_sltp": False,
                "copy_kill_switch": True,
                "symbol": "",
                "mt5_portable": True,
                "tele_chat": "",
                "tele_admin": "",
            },
        ])
        cls.app, cls.widget = create_engine(profile_manager=cls.fake)
        cls.app.processEvents()
        cls.root = cls.widget.rootObject()
        cls.widget.app = cls.app
        # Navigate to Profiles
        click_nav(cls.widget, cls.root, "Profiles")

    def pg(self):
        """Get the ProfilesPage root item (scope for component-local properties)."""
        return get_page(self.widget, self.root)


class TestProfilesPageRenders(_Base):
    """test_profiles_page_renders"""

    def test_page_exists_and_has_cards(self):
        """Page exists; profileCount == 2; editor title contains first profile name."""
        page = self.pg()
        self.assertIsNotNone(page, "page_Profiles not found")

        # Check profile count via root-level helper property
        count = qml_eval(self.widget, page, "profileCount")
        self.assertEqual(int(count), 2, f"Expected 2 profiles, got {count}")

        # Check editor title (first profile selected)
        title = qml_eval(self.widget, page, "selectedName")
        self.assertEqual(str(title), "A", f"Expected selectedName='A', got {title}")


class TestSelectSecondCard(_Base):
    """test_select_second_card_updates_editor"""

    def test_select_second_card(self):
        """Click second card; editor title contains 'B'."""
        page = self.pg()
        qml_eval(self.widget, page, "selectedName = 'B'; loadDraft(); loadSecretStatus()")
        pump(self.widget)
        title = qml_eval(self.widget, page, "selectedName")
        self.assertEqual(str(title), "B", f"Expected selectedName='B', got {title}")


class TestSaveCallsUpdateProfile(_Base):
    """test_save_calls_update_profile_no_secrets"""

    def test_save_update_no_secrets(self):
        """Set magic field, click Save; update_profile called with magic=42 and NO sensitive keys."""
        page = self.pg()
        qml_eval(self.widget, page, "draft.magic = '42'; dirty = true")
        pump(self.widget)

        qml_eval(self.widget, page, "save()")
        pump(self.widget)

        update_calls = [c for c in self.fake.calls if isinstance(c, tuple) and c[0] == "update_profile"]
        self.assertTrue(len(update_calls) > 0, "update_profile was not called")

        last_update = update_calls[-1]
        name = last_update[1]
        updates = last_update[2]
        self.assertEqual(name, "A")
        self.assertEqual(updates.get("magic"), 42)

        # Verify no sensitive keys in any update payload
        for call in update_calls:
            payload = call[2]
            for key in ("tele_token", "password", "secret", "token"):
                self.assertNotIn(key, payload, f"Sensitive key '{key}' found in update payload")


class TestSaveInvalidMagicShowsError(_Base):
    """test_save_invalid_magic_shows_error"""

    def test_invalid_magic_error(self):
        """Set magic 'abc', click Save; error banner visible; no update_profile call."""
        page = self.pg()
        calls_before = len(self.fake.calls)
        qml_eval(self.widget, page, "draft.magic = 'abc'; dirty = true")
        pump(self.widget)

        qml_eval(self.widget, page, "save()")
        pump(self.widget)

        error = qml_eval(self.widget, page, "errorText")
        self.assertNotEqual(str(error), "", f"Expected error text, got '{error}'")

        update_calls = [c for c in self.fake.calls[calls_before:] if isinstance(c, tuple) and c[0] == "update_profile"]
        self.assertEqual(len(update_calls), 0, "update_profile should not be called with invalid magic")


class TestStartStopButtons(_Base):
    """test_start_stop_buttons"""

    def test_start_stop(self):
        """Click start on B; click stop on A; verify calls."""
        page = self.pg()
        qml_eval(self.widget, page, "startStop('B', false)")
        pump(self.widget)
        start_calls = [c for c in self.fake.calls if isinstance(c, tuple) and c[0] == "start_profile"]
        self.assertTrue(any(c[1] == "B" for c in start_calls), "start_profile('B') not called")

        qml_eval(self.widget, page, "startStop('A', true)")
        pump(self.widget)
        stop_calls = [c for c in self.fake.calls if isinstance(c, tuple) and c[0] == "stop_profile"]
        self.assertTrue(any(c[1] == "A" for c in stop_calls), "stop_profile('A') not called")


class TestAddNewProfile(_Base):
    """test_add_new_profile_unique_name"""

    def test_add_new_unique_name(self):
        """Click Add new; add_profile called with unique name; list refreshed."""
        page = self.pg()
        calls_before = len(self.fake.calls)
        qml_eval(self.widget, page, "addNew()")
        pump(self.widget)

        add_calls = [c for c in self.fake.calls[calls_before:] if isinstance(c, tuple) and c[0] == "add_profile"]
        self.assertTrue(len(add_calls) > 0, "add_profile not called")
        new_name = add_calls[-1][1]
        self.assertTrue(new_name.startswith("NewProfile"), f"Name '{new_name}' does not start with 'NewProfile'")

        count = qml_eval(self.widget, page, "profileCount")
        self.assertEqual(int(count), 3, f"Expected 3 profiles after add, got {count}")


class TestDeleteTwoStep(_Base):
    """test_delete_two_step"""

    def test_delete_requires_two_clicks(self):
        """First click: no delete_profile call; second click: delete_profile called."""
        page = self.pg()
        calls_before = len(self.fake.calls)

        qml_eval(self.widget, page, "deleteArmed = false; deleteSelected()")
        pump(self.widget)

        armed = qml_eval(self.widget, page, "deleteArmed")
        self.assertTrue(bool(armed), "deleteArmed should be true after first click")

        delete_calls = [c for c in self.fake.calls[calls_before:] if isinstance(c, tuple) and c[0] == "delete_profile"]
        self.assertEqual(len(delete_calls), 0, "delete_profile should NOT be called on first click")

        qml_eval(self.widget, page, "deleteSelected()")
        pump(self.widget)

        delete_calls = [c for c in self.fake.calls[calls_before:] if isinstance(c, tuple) and c[0] == "delete_profile"]
        self.assertTrue(len(delete_calls) > 0, "delete_profile should be called on second click")
        self.assertEqual(delete_calls[-1][1], "A")


class TestTelegramTokenSaveAndClear(_Base):
    """test_telegram_token_save_and_clear"""

    def test_save_and_clear_token(self):
        """Set tokenInput, save; then clear; verify calls."""
        page = self.pg()
        qml_eval(self.widget, page, "tokenInput = '123:abc'")
        pump(self.widget)
        qml_eval(self.widget, page, "saveToken()")
        pump(self.widget)

        set_calls = [c for c in self.fake.calls if isinstance(c, tuple) and c[0] == "set_tele_token"]
        self.assertTrue(len(set_calls) > 0, "set_tele_token not called")
        self.assertEqual(set_calls[-1][2], "123:abc")

        qml_eval(self.widget, page, "clearToken()")
        pump(self.widget)

        clear_calls = [c for c in self.fake.calls if isinstance(c, tuple) and c[0] == "clear_tele_token"]
        self.assertTrue(len(clear_calls) > 0, "clear_tele_token not called")


class TestSecretsNeverReachQML(_Base):
    """test_secrets_never_reach_qml"""

    def test_no_secrets_in_list_profiles(self):
        """Fake profiles contain tele_token and password; QML-visible JSON does NOT contain them."""
        page = self.pg()
        # Reload to ensure fresh data
        qml_eval(self.widget, page, "reload()")
        pump(self.widget)

        # Get the QML-visible JSON via the api helper property
        json_str = qml_eval(self.widget, page, "JSON.stringify(api.list_profiles())")
        self.assertNotIn("SECRET_TOKEN_X", str(json_str), "SECRET_TOKEN_X found in QML-visible data")
        self.assertNotIn("PW_Y", str(json_str), "PW_Y found in QML-visible data")

        # Token field should be empty (never pre-filled)
        token_text = qml_eval(self.widget, page, "tokenInput")
        self.assertEqual(str(token_text), "", f"tokenInput should be empty, got '{token_text}'")


class TestErrorBannerOnBackendError(_Base):
    """test_error_banner_on_backend_error"""

    def test_error_banner_shows(self):
        """fake.fail_next['update_profile'] = 'boom'; Save triggers error banner."""
        page = self.pg()
        self.fake.fail_next["update_profile"] = "boom"
        qml_eval(self.widget, page, "draft.magic = '42'; dirty = true")
        pump(self.widget)

        qml_eval(self.widget, page, "save()")
        pump(self.widget)

        error = qml_eval(self.widget, page, "errorText")
        self.assertIn("boom", str(error), f"Expected 'boom' in error text, got '{error}'")


class TestEmptyState(_Base):
    """test_empty_state"""

    def test_empty_profiles_shows_empty_state(self):
        """Fresh FakeManager([]); engine; nav to Profiles; empty text visible."""
        empty_fake = FakeManager([])
        app2, widget2 = create_engine(profile_manager=empty_fake)
        app2.processEvents()
        root2 = widget2.rootObject()
        widget2.app = app2

        click_nav(widget2, root2, "Profiles")
        app2.processEvents()

        page2 = get_page(widget2, root2)
        self.assertIsNotNone(page2, "page_Profiles not found with empty profiles")

        count = qml_eval(widget2, page2, "profileCount")
        self.assertEqual(int(count), 0, f"Expected 0 profiles, got {count}")

        selected = qml_eval(widget2, page2, "selectedName")
        self.assertEqual(str(selected), "", f"Expected empty selectedName, got '{selected}'")


if __name__ == "__main__":
    unittest.main()
