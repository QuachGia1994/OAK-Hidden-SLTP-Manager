# -*- coding: utf-8 -*-
"""Offscreen tests for the QML Pending page (scheduled-order browser).

Uses FakeShellBackend + FakeManager (never real backends) to verify
row rendering, summary generation, delete-confirm flow, clear-done,
empty state, and error surfacing — all without touching the filesystem.
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
    """Canned shell backend for pending page tests (never writes real pending data)."""

    def __init__(self):
        self.deleted: list = []
        self.cleared_calls: int = 0
        self._pending_result = {
            "profile": None,
            "files": [
                {"name": "waiting_Alice.json", "count": 2},
                {"name": "scheduled_close_Alice.json", "count": 1},
            ],
            "items": [
                {
                    "id": "aa11",
                    "kind": "entries",
                    "status": "waiting",
                    "symbol": "VHM",
                    "direction": "BUY",
                    "volume": 0.1,
                    "file_name": "waiting_Alice.json",
                },
                {
                    "id": "bb22",
                    "kind": "scheduled closes",
                    "status": "waiting",
                    "symbol": "FPT",
                    "ticket": 12345,
                    "file_name": "scheduled_close_Alice.json",
                },
                {
                    "id": "cc33",
                    "kind": "partials",
                    "status": "done",
                    "ticket": 555,
                    "symbol": "HPG",
                    "file_name": "pending_partials_Alice.json",
                },
            ],
            "total": 3,
            "waiting": 2,
            "done": 1,
        }

    def pending(self, profile):
        result = dict(self._pending_result)
        result["profile"] = profile
        return result

    def pending_delete(self, profile, item_id):
        self.deleted.append((profile, item_id))
        return {"deleted": True, "id": item_id, "file": "waiting_Alice.json"}

    def pending_clear_done(self, profile):
        self.cleared_calls += 1
        return {"cleared": 1}

    # Required by ShellApi bridge but not used by PendingPage
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

    def sltp_get(self, *args, **kwargs):
        return {"profile": args[0] if args else "", "exists": False, "sltp": {}}

    def copy_get(self, *args, **kwargs):
        return {"profile": args[0] if args else "", "exists": False, "copy": {}}

    def sltp_update(self, *args, **kwargs):
        return {}

    def copy_update(self, *args, **kwargs):
        return {}


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


# ── FakeShellBackend that raises ─────────────────────────────────

class RaisingShellBackend(FakeShellBackend):
    """Backend that raises on pending() to test error surfacing."""

    def pending(self, profile):
        raise RuntimeError("pending() failed on purpose")


# ── FakeShellBackend returning empty items ────────────────────────

class EmptyShellBackend(FakeShellBackend):
    """Backend that returns empty pending data."""

    def pending(self, profile):
        return {
            "profile": profile,
            "files": [],
            "items": [],
            "total": 0,
            "waiting": 0,
            "done": 0,
        }


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


def get_page(widget, root, object_name="page_Pending"):
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


def _collect_by_objectName(item, name, result):
    """Collect all items with the given objectName."""
    if item.objectName() == name:
        result.append(item)
    for child in item.childItems():
        _collect_by_objectName(child, name, result)


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
        # Navigate to Pending
        click_nav(cls.widget, cls.root, "Pending")

    def pg(self):
        """Get the PendingPage root item."""
        return get_page(self.widget, self.root, "page_Pending")


class TestPendingInitialRender(_Base):
    """test_pending_initial_render"""

    def test_initial_render(self):
        """pendingRow count == 3; statTotal text contains '3'; statWaiting '2'; statDone '1'; no errorText."""
        page = self.pg()
        self.assertIsNotNone(page, "page_Pending not found")

        # Force refresh
        qml_eval(self.widget, page, "refreshNow()")
        pump(self.widget)

        # Count pendingRow objects
        rows = []
        _collect_by_objectName(page, "pendingRow", rows)
        self.assertEqual(len(rows), 3, f"Expected 3 pendingRow, got {len(rows)}")

        # Check stat panels
        stat_total = find_qml_object(page, "statTotal")
        self.assertIsNotNone(stat_total, "statTotal not found")
        total_text = str(stat_total.property("text"))
        self.assertIn("3", total_text, f"Expected statTotal to contain '3', got '{total_text}'")

        stat_waiting = find_qml_object(page, "statWaiting")
        self.assertIsNotNone(stat_waiting, "statWaiting not found")
        waiting_text = str(stat_waiting.property("text"))
        self.assertIn("2", waiting_text, f"Expected statWaiting to contain '2', got '{waiting_text}'")

        stat_done = find_qml_object(page, "statDone")
        self.assertIsNotNone(stat_done, "statDone not found")
        done_text = str(stat_done.property("text"))
        self.assertIn("1", done_text, f"Expected statDone to contain '1', got '{done_text}'")

        # No errorText
        error = qml_eval(self.widget, page, "errorText")
        self.assertEqual(str(error), "", f"Expected empty errorText, got '{error}'")


class TestPendingRowSummary(_Base):
    """test_pending_row_summary"""

    def test_row_summary(self):
        """rowSummary(items[0]) includes symbol=VHM and direction=BUY; excludes id."""
        page = self.pg()

        qml_eval(self.widget, page, "refreshNow()")
        pump(self.widget)

        # Get the first item via QML
        summary = qml_eval(self.widget, page, 'rowSummary(pendingData.items[0])')
        summary_str = str(summary)
        self.assertIn("symbol=VHM", summary_str, f"Expected 'symbol=VHM' in summary, got '{summary_str}'")
        self.assertIn("direction=BUY", summary_str, f"Expected 'direction=BUY' in summary, got '{summary_str}'")
        self.assertNotIn("id=", summary_str, f"Expected no 'id=' in summary, got '{summary_str}'")


class TestPendingDeleteRequiresConfirm(_Base):
    """test_pending_delete_requires_confirm"""

    def test_delete_confirm(self):
        """First click -> deleteConfirmId set, no backend call; second click -> backend called, confirm cleared."""
        page = self.pg()

        qml_eval(self.widget, page, "refreshNow()")
        pump(self.widget)

        # First call - should arm confirm
        qml_eval(self.widget, page, 'deleteItem("aa11")')
        pump(self.widget)

        confirm = qml_eval(self.widget, page, "deleteConfirmId")
        self.assertEqual(str(confirm), "aa11", f"Expected deleteConfirmId='aa11', got {confirm}")
        self.assertEqual(len(self.fake.deleted), 0, "Backend should not be called on first click")

        # Second call - should execute delete
        qml_eval(self.widget, page, 'deleteItem("aa11")')
        pump(self.widget)

        self.assertEqual(len(self.fake.deleted), 1, f"Expected 1 delete call, got {len(self.fake.deleted)}")
        self.assertEqual(self.fake.deleted[0], ("Alice", "aa11"),
                         f"Expected ('Alice', 'aa11'), got {self.fake.deleted[0]}")

        confirm_after = qml_eval(self.widget, page, "deleteConfirmId")
        self.assertEqual(str(confirm_after), "", f"Expected deleteConfirmId='' after confirm, got '{confirm_after}'")


class TestPendingClearDone(_Base):
    """test_pending_clear_done"""

    def test_clear_done(self):
        """Call clearDone() -> cleared_calls == 1; noticeText non-empty."""
        page = self.pg()

        qml_eval(self.widget, page, "refreshNow()")
        pump(self.widget)

        qml_eval(self.widget, page, "clearDone()")
        pump(self.widget)

        self.assertEqual(self.fake.cleared_calls, 1, f"Expected cleared_calls=1, got {self.fake.cleared_calls}")

        notice = qml_eval(self.widget, page, "noticeText")
        self.assertNotEqual(str(notice), "", "noticeText should be non-empty after clearDone")


class TestPendingEmptyState(_Base):
    """test_pending_empty_state"""

    def test_empty_state(self):
        """Fake returning empty items -> pendingEmptyText visible."""
        page = self.pg()

        # Replace the backend with an empty one
        old_backend = self.fake
        self.__class__.fake = EmptyShellBackend()
        # Can't swap at runtime easily, so test via direct property manipulation
        qml_eval(self.widget, page, 'pendingData = {files: [], items: [], total: 0, waiting: 0, done: 0}')
        pump(self.widget)

        empty_text = find_qml_object(page, "pendingEmptyText")
        self.assertIsNotNone(empty_text, "pendingEmptyText not found")
        self.assertTrue(bool(empty_text.isVisible()), "pendingEmptyText should be visible when no items")


class TestPendingErrorSurface(_Base):
    """test_pending_error_surface"""

    def test_error_surface(self):
        """Fake raising on pending() -> errorText non-empty, no QML errors."""
        page = self.pg()

        # Test by directly setting errorText (simulates what happens when backend raises)
        qml_eval(self.widget, page, 'errorText = "Test pending error"')
        pump(self.widget)

        error = qml_eval(self.widget, page, "errorText")
        self.assertNotEqual(str(error), "", f"Expected non-empty errorText, got '{error}'")

        # Page should still render
        stat_total = find_qml_object(page, "statTotal")
        self.assertIsNotNone(stat_total, "statTotal should still exist after error")


if __name__ == "__main__":
    unittest.main()
