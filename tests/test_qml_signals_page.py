# -*- coding: utf-8 -*-
"""Offscreen tests for the QML Signals page.

Uses FakeShellBackend + FakeManager (never real backends) to verify
service lifecycle UI, confirm flow, on-demand handling, logs grouping,
and profile selection — all without touching the filesystem or starting
any subprocesses.
"""
from __future__ import annotations

import os
import sys
import time
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
    """Canned shell backend for signals page tests (never starts real services)."""

    def __init__(self):
        self.starts: list = []
        self.stops: list = []
        self.services_payload: list = [
            {
                "key": "telegram", "label": "MiMo Telegram Bot",
                "kind": "subprocess", "configured": True, "status": "running",
                "pid": 1234, "exit_code": None, "trading_risk": "critical",
                "execution_armed": True, "note": "Telegram bot service",
                "config_note": "", "scope": "global",
            },
            {
                "key": "mimo_worker", "label": "MiMo Worker",
                "kind": "subprocess", "configured": True, "status": "running",
                "pid": 5678, "exit_code": None, "trading_risk": "none",
                "execution_armed": False, "note": "Worker process",
                "config_note": "", "scope": "global",
            },
            {
                "key": "factcheck_worker", "label": "FactCheck Worker",
                "kind": "subprocess", "configured": True, "status": "stopped",
                "pid": None, "exit_code": None, "trading_risk": "none",
                "execution_armed": False, "note": "Fact-checking service",
                "config_note": "", "scope": "global",
            },
            {
                "key": "screener", "label": "Stock Screener",
                "kind": "on_demand", "configured": True, "status": "stopped",
                "pid": None, "exit_code": None, "trading_risk": "none",
                "execution_armed": False, "note": "On-demand screener",
                "config_note": "", "scope": "global",
            },
            {
                "key": "signal_bot", "label": "Signal Bot",
                "kind": "subprocess", "configured": True, "status": "stopped",
                "pid": None, "exit_code": None, "trading_risk": "critical",
                "execution_armed": False, "note": "Signal bot service",
                "config_note": "", "scope": "profile",
            },
        ]

    def services(self):
        return self.services_payload

    def logs_tail(self, lines=200, query="", level="ALL"):
        return {
            "lines": [
                "[services] boot",
                "[svc:telegram] hello world",
                "[svc:mimo_worker] processing batch",
                "[svc:telegram] message sent",
            ],
            "truncated": False,
            "requested": lines,
            "latest_log": "oak.log",
        }

    def service_start(self, key, profile, confirm):
        self.starts.append((key, profile, confirm))
        return {"started": True, "pid": 1234, "status": "running"}

    def service_stop(self, key):
        self.stops.append(key)
        return {"stopped": True}

    def screener(self, limit=1000):
        return []

    def run_filter(self, limit=30):
        return {"ok": True, "status": "NO_DATA", "as_of_date": None, "scanned": 0,
                "buy": 0, "sell": 0, "recommendations": []}


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


def click_nav(widget, root, name: str):
    """Navigate to a sidebar page and process events."""
    qml_eval(widget, root, f'clickNav("{name}")')
    widget.app.processEvents()
    widget.grab()
    for _ in range(6):
        widget.app.processEvents()
        widget.grab()


def get_page(widget, root, object_name="page_Signals"):
    """Get a page root item from the StackView."""
    widget.app.processEvents()
    for _ in range(4):
        widget.grab()
        widget.app.processEvents()
    page = find_qml_object(root, object_name)
    return page


def pump(widget, n=6):
    """Pump events and force render."""
    for _ in range(n):
        widget.app.processEvents()
        widget.grab()


def jsval_to_list(val):
    """Convert a QJSValue or Python list to a plain Python list."""
    if val is None:
        return []
    if isinstance(val, list):
        return val
    # QJSValue — try to iterate via property access
    try:
        length = int(val.property("length"))
        return [val.property(str(i)) for i in range(length)]
    except Exception:
        pass
    try:
        return list(val)
    except Exception:
        return []


# ── Test classes ─────────────────────────────────────────────────

class _Base(unittest.TestCase):
    """Shared setUp: one QApplication + QQuickWidget per test class."""

    app: QApplication
    widget: QQuickWidget
    root: object
    fake: FakeShellBackend
    fake_manager: FakeManager

    @classmethod
    def setUpClass(cls):
        cls.fake = FakeShellBackend()
        cls.fake_manager = FakeManager()
        cls.app, cls.widget = create_engine(
            profile_manager=cls.fake_manager,
            shell_backend=cls.fake,
        )
        cls.app.processEvents()
        cls.engine_keep = cls.widget.engine()
        cls.root = cls.widget.rootObject()
        cls.widget.app = cls.app
        # Navigate to Signals
        click_nav(cls.widget, cls.root, "Signals")

    def pg(self):
        """Get the SignalsPage root item."""
        return get_page(self.widget, self.root, "page_Signals")

    def _find_card_by_key(self, key):
        """Find a service card by its key label text."""
        page = self.pg()
        return _find_card(page, key)


def _find_card(item, key):
    """Recursive search for a serviceCard containing a Text with the given key."""
    if item.objectName() == "serviceCard":
        # Check if any child Text has this key
        for child in item.childItems():
            if _has_text(child, key):
                return item
    for child in item.childItems():
        found = _find_card(child, key)
        if found is not None:
            return found
    return None


def _has_text(item, target):
    """Check if item is a Text with text == target."""
    try:
        t = item.property("text")
        if t is not None and str(t) == target:
            return True
    except Exception:
        pass
    for child in item.childItems():
        if _has_text(child, target):
            return True
    return False


def _collect_by_objectName(item, name, result):
    """Collect all items with the given objectName."""
    if item.objectName() == name:
        result.append(item)
    for child in item.childItems():
        _collect_by_objectName(child, name, result)


# ── Test classes ─────────────────────────────────────────────────

class TestSignalsRendersServiceCards(_Base):
    """test_signals_renders_service_cards"""

    def test_renders_cards(self):
        """Service card count == 5; runningServices == '2/5'; no errorText."""
        page = self.pg()
        self.assertIsNotNone(page, "page_Signals not found")

        # Force refresh to ensure data is loaded
        qml_eval(self.widget, page, "refreshNow()")
        pump(self.widget)

        running = qml_eval(self.widget, page, "runningServices")
        self.assertEqual(str(running), "2/5", f"Expected runningServices='2/5', got {running}")

        error = qml_eval(self.widget, page, "errorText")
        self.assertEqual(str(error), "", f"Expected empty errorText, got '{error}'")

        # Count serviceCard objects
        cards = []
        _collect_by_objectName(page, "serviceCard", cards)
        self.assertEqual(len(cards), 5, f"Expected 5 serviceCard, got {len(cards)}")


class TestCriticalStartRequiresConfirm(_Base):
    """test_signals_critical_start_requires_confirm"""

    def test_confirm_flow(self):
        """First click on telegram (critical) sets confirmKey; second click calls backend."""
        page = self.pg()

        # Verify telegram card exists
        card = self._find_card_by_key("telegram")
        self.assertIsNotNone(card, "telegram card not found")

        # First click via qml_eval — should set confirmKey, NOT call backend
        qml_eval(self.widget, page, 'startService("telegram")')
        pump(self.widget)

        confirm = qml_eval(self.widget, page, "confirmKey")
        self.assertEqual(str(confirm), "telegram", f"Expected confirmKey='telegram', got {confirm}")
        self.assertEqual(len(self.fake.starts), 0, "Backend should not be called on first click")

        # Second click via qml_eval — should call backend with confirm=true
        qml_eval(self.widget, page, 'doStart("telegram", true)')
        pump(self.widget)

        self.assertEqual(len(self.fake.starts), 1, f"Expected 1 start call, got {len(self.fake.starts)}")
        # selectedProfile is "Alice" (set by refreshNow from list_profiles)
        self.assertEqual(self.fake.starts[0][0], "telegram")
        self.assertEqual(self.fake.starts[0][2], True, "Expected confirm=True")


class TestConfirmExpires(_Base):
    """test_signals_confirm_expires"""

    def test_confirm_expires(self):
        """Click telegram (critical) -> confirmKey set; wait for timer -> confirmKey cleared."""
        page = self.pg()

        # Set confirmKey
        qml_eval(self.widget, page, 'confirmKey = "telegram"')
        pump(self.widget)

        confirm = qml_eval(self.widget, page, "confirmKey")
        self.assertEqual(str(confirm), "telegram", "confirmKey should be 'telegram'")

        # Wait for 8s timer + margin
        for _ in range(90):
            self.widget.app.processEvents()
            self.widget.grab()
        time.sleep(8.5)
        for _ in range(10):
            self.widget.app.processEvents()
            self.widget.grab()

        confirm_after = qml_eval(self.widget, page, "confirmKey")
        self.assertEqual(str(confirm_after), "", f"confirmKey should be empty after timer, got '{confirm_after}'")


class TestNonCriticalStartsDirectly(_Base):
    """test_signals_non_critical_starts_directly"""

    def test_direct_start(self):
        """Click factcheck_worker (non-critical, non-on_demand) -> starts directly."""
        page = self.pg()

        card = self._find_card_by_key("factcheck_worker")
        self.assertIsNotNone(card, "factcheck_worker card not found")

        qml_eval(self.widget, page, 'startService("factcheck_worker")')
        pump(self.widget)

        self.assertEqual(len(self.fake.starts), 1, f"Expected 1 start call, got {len(self.fake.starts)}")
        self.assertEqual(self.fake.starts[0][0], "factcheck_worker")
        self.assertEqual(self.fake.starts[0][2], False, "Expected confirm=False")


class TestOnDemandHasNoStartButton(_Base):
    """test_signals_on_demand_has_no_start_button"""

    def test_on_demand(self):
        """Screener card shows onDemandNote visible; calling startService sets noticeText."""
        page = self.pg()

        card = self._find_card_by_key("screener")
        self.assertIsNotNone(card, "screener card not found")

        on_demand_note = find_qml_object(card, "onDemandNote")
        self.assertIsNotNone(on_demand_note, "onDemandNote not found")
        self.assertTrue(bool(on_demand_note.isVisible()), "onDemandNote should be visible")

        # Calling startService via qml should set noticeText
        qml_eval(self.widget, page, 'startService("screener")')
        pump(self.widget)

        notice = qml_eval(self.widget, page, "noticeText")
        self.assertNotEqual(str(notice), "", "noticeText should be set for on_demand start")
        self.assertEqual(len(self.fake.starts), 0, "No start call for on_demand")


class TestStopCallsBackend(_Base):
    """test_signals_stop_calls_backend"""

    def test_stop(self):
        """Click mimo_worker (running) toggle -> stopService called."""
        page = self.pg()

        card = self._find_card_by_key("mimo_worker")
        self.assertIsNotNone(card, "mimo_worker card not found")

        qml_eval(self.widget, page, 'stopService("mimo_worker")')
        pump(self.widget)

        self.assertEqual(len(self.fake.stops), 1, f"Expected 1 stop call, got {len(self.fake.stops)}")
        self.assertEqual(self.fake.stops[0], "mimo_worker",
                         f"Expected stop for 'mimo_worker', got {self.fake.stops[0]}")


class TestLogsGrouped(_Base):
    """test_signals_logs_grouped"""

    def test_logs_per_service(self):
        """serviceLogs('telegram') includes [svc:telegram] hello world."""
        page = self.pg()

        # Ensure data loaded
        qml_eval(self.widget, page, "refreshNow()")
        pump(self.widget)

        # Check logLines is populated
        log_lines = qml_eval(self.widget, page, "logLines")
        log_count = qml_eval(self.widget, page, "logLines.length")
        self.assertTrue(int(log_count) > 0, f"Expected logLines to be populated, got length {log_count}")

        # Get serviceLogs via JSON.stringify to avoid QJSValue iteration issues
        logs_json = qml_eval(self.widget, page, 'JSON.stringify(serviceLogs("telegram"))')
        logs_str = str(logs_json)
        self.assertIn("[svc:telegram] hello world", logs_str,
                       f"Expected '[svc:telegram] hello world' in logs, got: {logs_str}")


class TestProfileSelectionUsedForStart(_Base):
    """test_signals_profile_selection_used_for_start"""

    def test_profile_used(self):
        """Click profile chip -> selectedProfile == 'Alice'; start signal_bot uses it."""
        page = self.pg()

        # Ensure data loaded
        qml_eval(self.widget, page, "refreshNow()")
        pump(self.widget)

        # Click the profile chip via qml_eval
        qml_eval(self.widget, page, 'selectProfile("Alice")')
        pump(self.widget)

        profile = qml_eval(self.widget, page, "selectedProfile")
        self.assertEqual(str(profile), "Alice", f"Expected selectedProfile='Alice', got {profile}")

        # Find signal_bot card (critical) and click twice
        card = self._find_card_by_key("signal_bot")
        self.assertIsNotNone(card, "signal_bot card not found")

        # First click -> confirm
        qml_eval(self.widget, page, 'startService("signal_bot")')
        pump(self.widget)

        confirm = qml_eval(self.widget, page, "confirmKey")
        self.assertEqual(str(confirm), "signal_bot", f"Expected confirmKey='signal_bot', got {confirm}")

        # Second click -> start with profile
        qml_eval(self.widget, page, 'doStart("signal_bot", true)')
        pump(self.widget)

        self.assertTrue(len(self.fake.starts) > 0, "Expected at least 1 start call")
        last_start = self.fake.starts[-1]
        self.assertEqual(last_start[0], "signal_bot")
        self.assertEqual(last_start[1], "Alice")
        self.assertEqual(last_start[2], True)


if __name__ == "__main__":
    unittest.main()
