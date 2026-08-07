# -*- coding: utf-8 -*-
"""Offscreen tests for the QML VN30 (local-EOD stock screener) page.

Uses FakeShellBackend (never real backends) to verify initial render,
search filtering, run-filter flow, empty state, and error surface.
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
    from PySide6.QtTest import QTest
except ImportError:
    raise unittest.SkipTest("PySide6 not installed")

# ── Ensure project root is on sys.path ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from oak_qml_app import create_engine  # noqa: E402


# ── FakeShellBackend ─────────────────────────────────────────────

class FakeShellBackend:
    """Canned shell backend for VN30 page tests."""

    def __init__(self):
        self.run_calls = 0
        self._screener_data = [
            {
                "date": "2026-08-06", "symbol": "VHM", "exchange": "HOSE",
                "open": 41.0, "high": 43.0, "low": 40.5, "close": 42.5,
                "volume": 1500000, "value": 63750000.0,
                "foreign_buy_value": 5000000.0, "foreign_sell_value": 3000000.0,
            },
            {
                "date": "2026-08-06", "symbol": "FPT", "exchange": "HOSE",
                "open": 120.0, "high": 125.0, "low": 119.0, "close": 124.0,
                "volume": 2000000, "value": 248000000.0,
                "foreign_buy_value": 10000000.0, "foreign_sell_value": 8000000.0,
            },
            {
                "date": "2026-08-06", "symbol": "HPG", "exchange": "HOSE",
                "open": 29.5, "high": 31.0, "low": 29.0, "close": 30.0,
                "volume": 3000000, "value": 90000000.0,
                "foreign_buy_value": 2000000.0, "foreign_sell_value": 4000000.0,
            },
        ]
        self._filter_result = {
            "ok": True,
            "status": "OK",
            "as_of_date": "2026-08-06",
            "scanned": 3,
            "buy": 1,
            "sell": 1,
            "recommendations": [
                {"symbol": "VHM", "direction": "BUY", "score": 2.5, "latest_close": 42.5, "rank": 1},
                {"symbol": "HPG", "direction": "SELL", "score": 1.0, "latest_close": 30.0, "rank": 2},
            ],
        }

    def services(self):
        return []

    def screener(self, limit=1000):
        return self._screener_data

    def run_filter(self, limit=30):
        self.run_calls += 1
        return self._filter_result

    def logs_tail(self, lines=200, query="", level="ALL"):
        return {"lines": [], "truncated": False, "requested": lines, "latest_log": None}

    def service_start(self, key, profile, confirm):
        return {"started": False, "reason": "not_applicable"}

    def service_stop(self, key):
        return {"stopped": False, "reason": "not_applicable"}


# ── FakeManager ──────────────────────────────────────────────────

class FakeManager:
    """Minimal profile manager for testing."""

    def __init__(self):
        self.profiles = {}

    def list_profiles(self):
        return {"profiles": []}

    def start_profile(self, name):
        return {"profile": name, "pid": 9999, "started": True}

    def stop_profile(self, name):
        return {"profile": name, "stopped": True}

    def add_profile(self, name, path="", magic=-1):
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
    fake: FakeShellBackend

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
        # VN30 is the initial page (initialItem: pageVN30)
        pump(cls.widget, 4)

    def pg(self):
        """Get the VN30Page root item."""
        self.widget.app.processEvents()
        for _ in range(4):
            self.widget.grab()
            self.widget.app.processEvents()
        page = find_qml_object(self.root, "page_VN30")
        return page


class TestVN30InitialRender(_Base):
    """test_vn30_initial_render"""

    def test_initial_render(self):
        """currentItem objectName == 'page_VN30'; stockRow count == 3; stockCountText contains '3'."""
        stack = find_qml_object(self.root, "contentStack")
        self.assertIsNotNone(stack, "contentStack not found")
        current = stack.property("currentItem")
        self.assertIsNotNone(current, "StackView has no current item")
        obj_name = current.property("objectName")
        self.assertEqual(obj_name, "page_VN30", f"Expected page_VN30, got {obj_name}")

        page = self.pg()
        self.assertIsNotNone(page, "page_VN30 not found")

        # Count stockRow items
        rows = []
        self._collect_rows(page, rows)
        self.assertEqual(len(rows), 3, f"Expected 3 stockRow, got {len(rows)}")

        count_text = qml_eval(self.widget, page, "stockCountText")
        self.assertIn("3", str(count_text), f"Expected '3' in stockCountText, got '{count_text}'")

    def _collect_rows(self, item, result):
        if item.objectName() == "stockRow":
            result.append(item)
        for child in item.childItems():
            self._collect_rows(child, result)


class TestVN30SearchFilters(_Base):
    """test_vn30_search_filters"""

    def test_search_filters(self):
        """Set search text 'VHM' -> filteredStocks().length == 1."""
        page = self.pg()

        qml_eval(self.widget, page, 'filterText = "VHM"')
        pump(self.widget)

        filtered = qml_eval(self.widget, page, "filteredStocks().length")
        self.assertEqual(int(filtered), 1, f"Expected filteredStocks length 1, got {filtered}")

        # Verify the symbol is VHM
        symbol = qml_eval(self.widget, page, "filteredStocks()[0].symbol")
        self.assertEqual(str(symbol), "VHM", f"Expected 'VHM', got '{symbol}'")


class TestVN30RunFilter(_Base):
    """test_vn30_run_filter"""

    def test_run_filter(self):
        """Run filter -> fake.run_calls == 1; recRow count == 2; filterResult.status == 'OK'."""
        page = self.pg()

        qml_eval(self.widget, page, "runFilterNow()")
        pump(self.widget)

        self.assertEqual(self.fake.run_calls, 1, f"Expected 1 run_filter call, got {self.fake.run_calls}")

        status = qml_eval(self.widget, page, "filterResult.status")
        self.assertEqual(str(status), "OK", f"Expected filterResult.status='OK', got {status}")

        # Count recRow items
        recs = []
        self._collect_recs(page, recs)
        self.assertEqual(len(recs), 2, f"Expected 2 recRow, got {len(recs)}")

    def _collect_recs(self, item, result):
        if item.objectName() == "recRow":
            result.append(item)
        for child in item.childItems():
            self._collect_recs(child, result)


class TestVN30EmptyState(_Base):
    """test_vn30_empty_state"""

    def test_empty_state(self):
        """Empty screener data -> stocksEmptyText visible; stockCountText contains '0'."""
        # Create a new engine with empty screener
        empty_fake = FakeShellBackend()
        empty_fake._screener_data = []
        empty_manager = FakeManager()
        app2, widget2 = create_engine(
            profile_manager=empty_manager,
            shell_backend=empty_fake,
        )
        app2.processEvents()
        root2 = widget2.rootObject()
        widget2.app = app2
        pump(widget2, 4)

        page = find_qml_object(root2, "page_VN30")
        self.assertIsNotNone(page, "page_VN30 not found")

        count_text = qml_eval(widget2, page, "stockCountText")
        self.assertIn("0", str(count_text), f"Expected '0' in stockCountText, got '{count_text}'")

        empty_text = find_qml_object(page, "stocksEmptyText")
        self.assertIsNotNone(empty_text, "stocksEmptyText not found")
        self.assertTrue(bool(empty_text.isVisible()), "stocksEmptyText should be visible")


class TestVN30ErrorSurface(_Base):
    """test_vn30_error_surface"""

    def test_error_surface(self):
        """screener() raising RuntimeError -> errorText non-empty and page still renders."""
        # Create engine with a backend that raises on screener()
        class ErrorBackend(FakeShellBackend):
            def screener(self, limit=1000):
                raise RuntimeError("boom")

        error_fake = ErrorBackend()
        error_manager = FakeManager()
        app2, widget2 = create_engine(
            profile_manager=error_manager,
            shell_backend=error_fake,
        )
        app2.processEvents()
        root2 = widget2.rootObject()
        widget2.app = app2
        pump(widget2, 4)

        page = find_qml_object(root2, "page_VN30")
        self.assertIsNotNone(page, "page_VN30 not found")

        error = qml_eval(widget2, page, "errorText")
        self.assertNotEqual(str(error), "", f"Expected non-empty errorText, got '{error}'")

        # Verify no QML errors
        self.assertEqual(len(widget2.errors()), 0, f"QML errors found: {widget2.errors()}")


if __name__ == "__main__":
    unittest.main()
