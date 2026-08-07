# -*- coding: utf-8 -*-
"""Offscreen tests for QML theme/lang persistence at boot and sidebar rail.

Verifies that:
  - settings.json theme/lang is applied at boot via Component.onCompleted
  - Sidebar rail toggles persist via ShellApi.settings_update
  - Graceful fallback when settings.json is missing or backend errors

Uses FakeShellBackend + FakeManager (or real ShellBackend with temp dir)
to verify behavior without touching production settings.json.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

# ── Env MUST be set before any Qt import ──
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_QPA_FONTDIR"] = r"C:\Windows\Fonts"

try:
    from PySide6.QtCore import Qt
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


# ── FakeShellBackend ─────────────────────────────────────────────

class FakeShellBackend:
    """Canned shell backend for theme persist tests."""

    def __init__(self):
        self.settings_get_calls: list = []
        self.settings_update_calls: list = []

    def settings_get(self):
        self.settings_get_calls.append(True)
        return {"ok": True, "result": {"theme": "dark", "lang": "VN"}}

    def settings_update(self, updates):
        self.settings_update_calls.append(updates)
        parsed = json.loads(updates) if isinstance(updates, str) else updates
        return {"ok": True, "result": parsed}

    # Required by ShellApi bridge but not used by theme persist tests
    def services(self):
        return []

    def logs_tail(self, *args, **kwargs):
        return {"lines": [], "truncated": False, "requested": 200, "latest_log": ""}

    def service_start(self, *args, **kwargs):
        return {"started": False}

    def service_stop(self, *args, **kwargs):
        return {"stopped": False}

    def screener(self, *args, **kwargs):
        return []

    def run_filter(self, *args, **kwargs):
        return {}

    def pending(self, *args, **kwargs):
        return {"files": [], "items": [], "total": 0, "waiting": 0, "done": 0}

    def pending_delete(self, *args, **kwargs):
        return {"deleted": False}

    def pending_clear_done(self, *args, **kwargs):
        return {"cleared": 0}

    def copy_get(self, *args, **kwargs):
        return {"profile": "", "exists": False, "copy": {}}

    def copy_update(self, *args, **kwargs):
        return {"profile": "", "exists": False, "copy": {}}

    def sltp_get(self, *args, **kwargs):
        return {"profile": "", "exists": False, "sltp": {}}

    def sltp_update(self, *args, **kwargs):
        return {"profile": "", "exists": False, "sltp": {}}

    def diagnostics(self):
        return {"mode": "source", "python": "3.12.0", "root_name": "ROBOT SLTP", "profiles": 2, "settings": True}

    def export_bundle(self):
        return {"exported": False}


# ── FakeManager ──────────────────────────────────────────────────

class FakeManager:
    """In-memory profile manager for testing."""

    def __init__(self):
        self.profiles = {
            "Alice": {
                "profile_name": "Alice",
                "status": "running",
                "path": r"C:\data\Alice",
            },
        }
        self.calls: list = []

    def list_profiles(self):
        self.calls.append("list_profiles")
        return {"profiles": [dict(p) for p in self.profiles.values()]}

    def start_profile(self, name):
        self.calls.append(("start_profile", name))
        return {"profile": name, "pid": 9999, "started": True}

    def stop_profile(self, name):
        self.calls.append(("stop_profile", name))
        return {"profile": name, "stopped": True}

    def add_profile(self, name, path="", magic=-1):
        self.calls.append(("add_profile", name))
        return {"profile_name": name, "status": "stopped", "pid": None}

    def running_workers(self):
        return []


# ── RaisingShellBackend ──────────────────────────────────────────

class RaisingShellBackend(FakeShellBackend):
    """Backend that raises on settings_get to test error surfacing."""

    def settings_get(self):
        raise RuntimeError("settings_get failed on purpose")


# ── Helpers ──────────────────────────────────────────────────────

def qml_eval(widget, scope, expr: str):
    """Evaluate a QML expression with *scope* as the context object."""
    ctx = widget.engine().rootContext()
    e = QQmlExpression(ctx, scope, expr)
    result = e.evaluate()
    err = e.error()
    if err.isValid():
        raise RuntimeError(f"QML eval error: {err.toString()}")
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


def pump(widget, n=6):
    """Pump events and force render."""
    for _ in range(n):
        widget.app.processEvents()
        widget.grab()


# ── Test classes ─────────────────────────────────────────────────


class TestBootAppliesPersistedSettings(unittest.TestCase):
    """Boot with settings.json {"theme":"light","lang":"EN"} applies at startup."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="oak_theme_")
        settings_path = os.path.join(cls.tmp, "settings.json")
        with open(settings_path, "w") as f:
            json.dump({"theme": "light", "lang": "EN"}, f)

        # Set env BEFORE create_engine so real ShellBackend reads from tmp
        os.environ["OAK_DATA_DIR"] = cls.tmp

        cls.app, cls.widget = create_engine(
            profile_manager=FakeManager(),
            # No shell_backend — use real ShellBackend reading temp settings.json
        )
        cls.app.processEvents()
        cls.root = cls.widget.rootObject()
        cls.widget.app = cls.app

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("OAK_DATA_DIR", None)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_boot_applies_persisted_settings(self):
        """currentTheme=='light' and currentLang=='EN' after boot."""
        pump(self.widget)
        theme = self.root.property("currentTheme")
        lang = self.root.property("currentLang")
        self.assertEqual(str(theme), "light", f"Expected currentTheme='light', got {theme}")
        self.assertEqual(str(lang), "EN", f"Expected currentLang='EN', got {lang}")


class TestBootFallbackDefaults(unittest.TestCase):
    """Boot with empty temp dir (no settings.json) keeps defaults."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="oak_theme_")
        # Empty dir — no settings.json file

        os.environ["OAK_DATA_DIR"] = cls.tmp

        cls.app, cls.widget = create_engine(
            profile_manager=FakeManager(),
            # No shell_backend — real ShellBackend reads empty temp dir
        )
        cls.app.processEvents()
        cls.root = cls.widget.rootObject()
        cls.widget.app = cls.app

    @classmethod
    def tearDownClass(cls):
        os.environ.pop("OAK_DATA_DIR", None)
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_boot_fallback_defaults(self):
        """currentTheme=='dark' and currentLang=='VN' when no settings.json."""
        pump(self.widget)
        theme = self.root.property("currentTheme")
        lang = self.root.property("currentLang")
        self.assertEqual(str(theme), "dark", f"Expected currentTheme='dark', got {theme}")
        self.assertEqual(str(lang), "VN", f"Expected currentLang='VN', got {lang}")


class TestBootToleratesSettingsError(unittest.TestCase):
    """Boot with backend that raises on settings_get does not crash."""

    @classmethod
    def setUpClass(cls):
        cls.app, cls.widget = create_engine(
            profile_manager=FakeManager(),
            shell_backend=RaisingShellBackend(),
        )
        cls.app.processEvents()
        cls.root = cls.widget.rootObject()
        cls.widget.app = cls.app

    def test_boot_tolerates_settings_error(self):
        """Engine loads without crash; defaults kept (dark/VN)."""
        pump(self.widget)
        theme = self.root.property("currentTheme")
        lang = self.root.property("currentLang")
        self.assertEqual(str(theme), "dark", f"Expected currentTheme='dark', got {theme}")
        self.assertEqual(str(lang), "VN", f"Expected currentLang='VN', got {lang}")


class TestSidebarRailPersists(unittest.TestCase):
    """Sidebar rail toggles persist via ShellApi.settings_update."""

    @classmethod
    def setUpClass(cls):
        cls.fake = FakeShellBackend()
        cls.app, cls.widget = create_engine(
            profile_manager=FakeManager(),
            shell_backend=cls.fake,
        )
        cls.app.processEvents()
        cls.root = cls.widget.rootObject()
        cls.widget.app = cls.app
        pump(cls.widget)

    def test_theme_toggle_persists(self):
        """toggleThemePersistPython() calls settings_update with theme payload."""
        qml_eval(self.widget, self.root, "toggleThemePersistPython()")
        pump(self.widget)

        # Should have at least one settings_update call
        self.assertGreaterEqual(len(self.fake.settings_update_calls), 1,
                                f"Expected >=1 settings_update call, got {len(self.fake.settings_update_calls)}")

        # Parse last payload
        last = self.fake.settings_update_calls[-1]
        parsed = json.loads(last) if isinstance(last, str) else last
        self.assertIn("theme", parsed, f"Expected 'theme' key in payload, got {parsed}")
        self.assertEqual(parsed["theme"], "light",
                         f"Expected theme='light' (toggled from dark), got {parsed['theme']}")

        # Verify currentTheme property updated
        current_theme = self.root.property("currentTheme")
        self.assertEqual(str(current_theme), "light",
                         f"Expected currentTheme='light', got {current_theme}")

    def test_lang_toggle_persists(self):
        """setLangPersistPython('VN') calls settings_update with lang payload."""
        qml_eval(self.widget, self.root, 'setLangPersistPython("VN")')
        pump(self.widget)

        # Should have at least one settings_update call
        self.assertGreaterEqual(len(self.fake.settings_update_calls), 1,
                                f"Expected >=1 settings_update call, got {len(self.fake.settings_update_calls)}")

        # Parse last payload
        last = self.fake.settings_update_calls[-1]
        parsed = json.loads(last) if isinstance(last, str) else last
        self.assertIn("lang", parsed, f"Expected 'lang' key in payload, got {parsed}")
        self.assertEqual(parsed["lang"], "VN",
                         f"Expected lang='VN', got {parsed['lang']}")

        # Verify currentLang property updated
        current_lang = self.root.property("currentLang")
        self.assertEqual(str(current_lang), "VN",
                         f"Expected currentLang='VN', got {current_lang}")


if __name__ == "__main__":
    unittest.main()
