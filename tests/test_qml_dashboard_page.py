# -*- coding: utf-8 -*-
"""Offscreen tests for the QML Dashboard page (Phase 2).

Uses FakeManager + FakeDashboardBackend (never real backends) to verify
bridge wiring, UI rendering, and data flow without touching the filesystem
or starting any subprocesses.
"""
from __future__ import annotations

import json
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
    from PySide6.QtTest import QTest
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

    def __init__(self, profiles=None):
        if profiles is None:
            profiles = []
        self.profiles = {p["profile_name"]: dict(p) for p in profiles}
        self.calls: list = []
        self.fail_next: dict[str, str] = {}

    def list_profiles(self):
        self.calls.append("list_profiles")
        return {"profiles": [dict(p) for p in self.profiles.values()]}

    def running_workers(self):
        return [name for name, p in self.profiles.items() if p.get("status") == "running"]

    def start_profile(self, name):
        self.calls.append(("start_profile", name))
        if "start_profile" in self.fail_next:
            msg = self.fail_next.pop("start_profile")
            raise RuntimeError(msg)
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


# ── FakeDashboardBackend ─────────────────────────────────────────

class FakeDashboardBackend:
    """Canned read-only data source for dashboard tests."""

    def __init__(self, manager, profiles=None, services=None, orders=None,
                 logs=None, handshake=None, health=None):
        self._manager = manager
        self._profiles_override = profiles
        self._services = services or [
            {"key": "telegram", "label": "MiMo Telegram Bot", "status": "running",
             "kind": "subprocess", "configured": True},
            {"key": "screener", "label": "Stock Screener", "status": "stopped",
             "kind": "on_demand", "configured": True},
        ]
        self._orders = orders or {
            "scheduled_trades": 1, "scheduled_closes": 2,
            "pending_partials": 3, "total": 6,
        }
        self._logs = logs or {
            "lines": ["[INFO] worker ready", "[INFO] heartbeat ok"],
            "truncated": False, "requested": 200, "latest_log": "oak.log",
        }
        self._handshake = handshake or {"app": "oak-core", "version": "9.9.9", "protocol": 1}
        self._health = health or {"status": "ok", "uptime": "00:00:05", "workers": ["A"], "protocol": 1}
        self.fail_next: dict[str, str] = {}
        self.overview_calls: int = 0

    def handshake(self):
        self._maybe_fail("handshake")
        return dict(self._handshake)

    def health(self):
        self._maybe_fail("health")
        return dict(self._health)

    def profiles(self):
        self._maybe_fail("profiles")
        self.overview_calls += 1
        if self._profiles_override is not None:
            return [dict(p) for p in self._profiles_override]
        payload = self._manager.list_profiles()
        return payload.get("profiles") or []

    def services(self):
        self._maybe_fail("services")
        return [dict(s) for s in self._services]

    def orders(self):
        self._maybe_fail("orders")
        return dict(self._orders)

    def logs(self, lines=200):
        self._maybe_fail("logs")
        return dict(self._logs)

    def _maybe_fail(self, method):
        if method in self.fail_next:
            msg = self.fail_next.pop(method)
            raise RuntimeError(msg)


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


def get_page(widget, root):
    """Get the DashboardPage root item from the StackView."""
    widget.app.processEvents()
    for _ in range(4):
        widget.grab()
        widget.app.processEvents()
    page = find_qml_object(root, "page_Dashboard")
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
    fake_backend: FakeDashboardBackend

    @classmethod
    def setUpClass(cls):
        cls.fake = FakeManager([
            {
                "profile_name": "A",
                "path": r"C:\MT5\A",
                "magic": 100,
                "status": "running",
                "pid": 1234,
                "tele_token": "SECRET_TOKEN_X",
                "password": "PW_Y",
            },
            {
                "profile_name": "B",
                "path": r"C:\MT5\B",
                "magic": 200,
                "status": "stopped",
                "pid": None,
            },
        ])
        cls.fake_backend = FakeDashboardBackend(cls.fake)
        cls.app, cls.widget = create_engine(
            profile_manager=cls.fake,
            dashboard_backend=cls.fake_backend,
        )
        cls.app.processEvents()
        cls.root = cls.widget.rootObject()
        cls.widget.app = cls.app
        # Navigate to Dashboard
        click_nav(cls.widget, cls.root, "Dashboard")

    def pg(self):
        """Get the DashboardPage root item."""
        return get_page(self.widget, self.root)


class TestDashboardPageRenders(_Base):
    """test_page_renders_data"""

    def test_renders_data(self):
        """Page exists; data properties are correct."""
        page = self.pg()
        self.assertIsNotNone(page, "page_Dashboard not found")

        profile_rows = qml_eval(self.widget, page, "profileRows")
        self.assertEqual(len(profile_rows), 2, f"Expected 2 profiles, got {len(profile_rows)}")

        running_count = qml_eval(self.widget, page, "runningCount")
        self.assertEqual(int(running_count), 1, f"Expected runningCount=1, got {running_count}")

        profile_total = qml_eval(self.widget, page, "profileTotal")
        self.assertEqual(int(profile_total), 2, f"Expected profileTotal=2, got {profile_total}")

        pending_total = qml_eval(self.widget, page, "pendingTotal")
        self.assertEqual(int(pending_total), 6, f"Expected pendingTotal=6, got {pending_total}")

        services_running = qml_eval(self.widget, page, "servicesRunning")
        self.assertEqual(int(services_running), 1, f"Expected servicesRunning=1, got {services_running}")

        health_status = qml_eval(self.widget, page, "healthStatus")
        self.assertEqual(str(health_status), "ok", f"Expected healthStatus='ok', got {health_status}")

        handshake_version = qml_eval(self.widget, page, "handshakeVersion")
        self.assertEqual(str(handshake_version), "9.9.9", f"Expected handshakeVersion='9.9.9', got {handshake_version}")

        log_lines = qml_eval(self.widget, page, "logLines")
        self.assertEqual(len(log_lines), 2, f"Expected 2 log lines, got {len(log_lines)}")

        # Header title text should be non-empty (check via objectName search)
        uptime_text = qml_eval(self.widget, page, "uptimeText")
        self.assertEqual(str(uptime_text), "00:00:05", f"Expected uptime='00:00:05', got {uptime_text}")


class TestRefreshPullsNewData(_Base):
    """test_refresh_pulls_new_data"""

    def test_refresh_pulls_new_data(self):
        """Mutate backend; call refreshNow(); assert new data."""
        page = self.pg()
        # Add profile C
        self.fake_backend._profiles_override = [
            {"profile_name": "A", "path": r"C:\MT5\A", "status": "running"},
            {"profile_name": "B", "path": r"C:\MT5\B", "status": "stopped"},
            {"profile_name": "C", "path": r"C:\MT5\C", "status": "stopped"},
        ]
        self.fake_backend._orders = {
            "scheduled_trades": 2, "scheduled_closes": 3,
            "pending_partials": 4, "total": 9,
        }
        qml_eval(self.widget, page, "refreshNow()")
        pump(self.widget)

        profile_rows = qml_eval(self.widget, page, "profileRows")
        self.assertEqual(len(profile_rows), 3, f"Expected 3 profiles after refresh, got {len(profile_rows)}")

        pending_total = qml_eval(self.widget, page, "pendingTotal")
        self.assertEqual(int(pending_total), 9, f"Expected pendingTotal=9, got {pending_total}")


class TestToggleStartStopCallsApi(_Base):
    """test_toggle_start_stop_calls_api"""

    def test_toggle_start_stop(self):
        """toggleProfile('B') starts B; toggleProfile('A') stops A."""
        page = self.pg()

        # Start B
        qml_eval(self.widget, page, "toggleProfile('B')")
        pump(self.widget)

        start_calls = [c for c in self.fake.calls if isinstance(c, tuple) and c[0] == "start_profile"]
        self.assertTrue(any(c[1] == "B" for c in start_calls), "start_profile('B') not called")

        # Verify B is running after refresh
        status_b = qml_eval(self.widget, page, "profileRows[1].status")
        self.assertEqual(str(status_b), "running", f"Expected B status='running', got {status_b}")

        # Stop A
        qml_eval(self.widget, page, "toggleProfile('A')")
        pump(self.widget)

        stop_calls = [c for c in self.fake.calls if isinstance(c, tuple) and c[0] == "stop_profile"]
        self.assertTrue(any(c[1] == "A" for c in stop_calls), "stop_profile('A') not called")

        # Verify A is stopped after refresh
        status_a = qml_eval(self.widget, page, "profileRows[0].status")
        self.assertEqual(str(status_a), "stopped", f"Expected A status='stopped', got {status_a}")


class TestErrorBanner(_Base):
    """test_error_banner"""

    def test_error_banner_on_health_failure(self):
        """health() raises RuntimeError('boom') → errorText contains 'boom'."""
        page = self.pg()

        # Set up failure
        self.fake_backend.fail_next["health"] = "boom"
        qml_eval(self.widget, page, "refreshNow()")
        pump(self.widget)

        error = qml_eval(self.widget, page, "errorText")
        self.assertIn("boom", str(error), f"Expected 'boom' in errorText, got '{error}'")

        # overview.ok should stay True (other fields still load)
        ok = qml_eval(self.widget, page, "overview.ok")
        self.assertTrue(bool(ok), "overview.ok should be True even when health fails")

        # Clear failure and refresh → errorText should be empty
        qml_eval(self.widget, page, "refreshNow()")
        pump(self.widget)
        error2 = qml_eval(self.widget, page, "errorText")
        self.assertEqual(str(error2), "", f"Expected empty errorText after clear, got '{error2}'")


class TestEmptyState(_Base):
    """test_empty_state"""

    def test_empty_profiles_and_logs(self):
        """Empty FakeManager + empty backend → profileRows.length=0, hasProfiles=false."""
        empty_fake = FakeManager([])
        empty_backend = FakeDashboardBackend(
            empty_fake,
            profiles=[],
            services=[],
            orders={"scheduled_trades": 0, "scheduled_closes": 0, "pending_partials": 0, "total": 0},
            logs={"lines": [], "truncated": False, "requested": 200, "latest_log": None},
        )
        app2, widget2 = create_engine(
            profile_manager=empty_fake,
            dashboard_backend=empty_backend,
        )
        app2.processEvents()
        root2 = widget2.rootObject()
        widget2.app = app2

        click_nav(widget2, root2, "Dashboard")
        app2.processEvents()

        page2 = get_page(widget2, root2)
        self.assertIsNotNone(page2, "page_Dashboard not found with empty data")

        profile_rows = qml_eval(widget2, page2, "profileRows")
        self.assertEqual(len(profile_rows), 0, f"Expected 0 profiles, got {len(profile_rows)}")

        has_profiles = qml_eval(widget2, page2, "hasProfiles")
        self.assertFalse(bool(has_profiles), "hasProfiles should be False")


class TestSecretsNeverReachQML(_Base):
    """test_secrets_never_reach_qml"""

    def test_no_secrets_in_overview(self):
        """overview() from Python should NOT contain sensitive values."""
        overview = self.widget.dashboardApi.overview()
        dump = json.dumps(overview)
        self.assertNotIn("SECRET_TOKEN_X", dump, "SECRET_TOKEN_X found in dashboard overview")
        self.assertNotIn("PW_Y", dump, "PW_Y found in dashboard overview")

    def test_no_secrets_in_qml_data(self):
        """QML profileRows should NOT contain sensitive values."""
        page = self.pg()
        qml_eval(self.widget, page, "refreshNow()")
        pump(self.widget)

        json_str = qml_eval(self.widget, page, "JSON.stringify(profileRows)")
        self.assertNotIn("SECRET_TOKEN_X", str(json_str), "SECRET_TOKEN_X found in QML profileRows")
        self.assertNotIn("PW_Y", str(json_str), "PW_Y found in QML profileRows")


class TestUptimeRenders(_Base):
    """test_uptime_renders"""

    def test_uptime_renders(self):
        """uptimeText should show the fake health uptime."""
        page = self.pg()
        uptime = qml_eval(self.widget, page, "uptimeText")
        self.assertEqual(str(uptime), "00:00:05", f"Expected uptimeText='00:00:05', got '{uptime}'")


class TestProfileRowFits(_Base):
    """test_profile_row_button_fits"""

    def test_toggle_button_within_row(self):
        """First delegate row (profile A, running -> widest 'ĐANG CHẠY' state):
        the toggle button right edge must not exceed the row width."""
        page = self.pg()
        row = find_qml_object(page, "profileRow")
        self.assertIsNotNone(row, "profileRow not found")
        btn = find_qml_object(row, "profileToggleBtn")
        self.assertIsNotNone(btn, "profileToggleBtn not found")
        right = int(btn.x()) + int(btn.width())
        row_w = int(row.width())
        self.assertLessEqual(right, row_w, f"toggle button right edge {right} > row width {row_w}")


class TestProfilesEmptyStateVisual(_Base):
    """test_profiles_empty_state_visual"""

    def test_empty_state_text_visible(self):
        """Empty FakeManager -> profilesEmptyText is visible and rendered."""
        empty_fake = FakeManager([])
        empty_backend = FakeDashboardBackend(
            empty_fake,
            profiles=[],
            services=[],
            orders={"scheduled_trades": 0, "scheduled_closes": 0, "pending_partials": 0, "total": 0},
            logs={"lines": [], "truncated": False, "requested": 200, "latest_log": None},
        )
        app2, widget2 = create_engine(profile_manager=empty_fake, dashboard_backend=empty_backend)
        app2.processEvents()
        root2 = widget2.rootObject()
        widget2.app = app2
        click_nav(widget2, root2, "Dashboard")
        app2.processEvents()
        page2 = get_page(widget2, root2)
        self.assertIsNotNone(page2, "page_Dashboard not found")
        empty_text = find_qml_object(page2, "profilesEmptyText")
        self.assertIsNotNone(empty_text, "profilesEmptyText not found")
        self.assertTrue(bool(empty_text.isVisible()), "profilesEmptyText should be visible with 0 profiles")


class TestDashTwoPanelRowFillsPage(_Base):
    """test_dash_two_panel_row_fills_page"""

    def test_two_panel_row_height_fills_page(self):
        """dashTwoPanelRow height >= 600 (before fix: 340, after: ~622)."""
        page = self.pg()
        row = find_qml_object(page, "dashTwoPanelRow")
        self.assertIsNotNone(row, "dashTwoPanelRow not found")
        h = int(row.height())
        self.assertGreaterEqual(h, 600, f"dashTwoPanelRow height {h} < 600 (expected ~622)")


class TestStartAllProfiles(_Base):
    """test_start_all_profiles"""

    def _arm_and_fire(self):
        qml_eval(self.widget, self.pg(), "toggleStartAll()")
        qml_eval(self.widget, self.pg(), "toggleStartAll()")
        pump(self.widget)

    def test_btn_present_visible_and_fits(self):
        """startAllBtn exists, visible with profiles, right edge within header row."""
        page = self.pg()
        btn = find_qml_object(page, "startAllBtn")
        self.assertIsNotNone(btn, "startAllBtn not found")
        self.assertTrue(bool(btn.isVisible()), "startAllBtn should be visible with 2 profiles")
        parent_w = float(qml_eval(self.widget, page, "parent.width"))
        btn_right = float(btn.x()) + float(btn.width())
        self.assertLessEqual(btn_right, parent_w + 1,
                             f"startAllBtn right edge {btn_right} > parent width {parent_w}")
        label = find_qml_object(page, "startAllText")
        self.assertIsNotNone(label, "startAllText not found")
        self.assertIn(str(label.property("text")), ("Chạy tất cả", "Start All"),
                      f"unexpected label {label.property('text')}")

    def test_two_step_confirm(self):
        """First click only arms (no start calls); second click starts idle profiles only."""
        page = self.pg()
        # Fresh call baseline: earlier tests in this class (pytest runs unittest
        # methods alphabetically) may have recorded start_profile calls already.
        self.fake.calls.clear()
        qml_eval(self.widget, page, "toggleStartAll()")
        pump(self.widget)
        armed = qml_eval(self.widget, page, "startAllArmed")
        self.assertTrue(bool(armed), "expected armed after first click")
        start_calls = [c for c in self.fake.calls if isinstance(c, tuple) and c[0] == "start_profile"]
        self.assertEqual(len(start_calls), 0, "no start call before second click")
        qml_eval(self.widget, page, "toggleStartAll()")
        pump(self.widget)
        start_calls = [c for c in self.fake.calls if isinstance(c, tuple) and c[0] == "start_profile"]
        names = sorted(c[1] for c in start_calls)
        self.assertEqual(names, ["B"], f"expected only B started, got {names}")
        armed = qml_eval(self.widget, page, "startAllArmed")
        self.assertFalse(bool(armed), "expected disarmed after firing")
        status_b = qml_eval(self.widget, page, "profileRows[1].status")
        self.assertEqual(str(status_b), "running", f"expected B running after refresh, got {status_b}")

    def test_disarm_on_timeout(self):
        """Armed state auto-disarms when the timer fires, without starting anything."""
        page = self.pg()
        qml_eval(self.widget, page, "startAllTimeout = 60")
        qml_eval(self.widget, page, "toggleStartAll()")
        pump(self.widget)
        self.assertTrue(bool(qml_eval(self.widget, page, "startAllArmed")), "expected armed")
        QTest.qWait(200)
        pump(self.widget)
        self.assertFalse(bool(qml_eval(self.widget, page, "startAllArmed")), "expected disarmed after timeout")
        start_calls = [c for c in self.fake.calls if isinstance(c, tuple) and c[0] == "start_profile"]
        self.assertEqual(len(start_calls), 0, "no start call after timeout")
        qml_eval(self.widget, page, "startAllTimeout = 2500")

    def test_error_surface_but_others_attempted(self):
        """When start_profile raises for one profile, errorText is set and remaining idle profiles are still attempted."""
        page = self.pg()
        self.fake_backend._profiles_override = [
            {"profile_name": "A", "path": r"C:\MT5\A", "status": "running"},
            {"profile_name": "B", "path": r"C:\MT5\B", "status": "stopped"},
            {"profile_name": "C", "path": r"C:\MT5\C", "status": "stopped"},
        ]
        qml_eval(self.widget, page, "refreshNow()")
        pump(self.widget)
        self.fake.fail_next["start_profile"] = "boom"
        self._arm_and_fire()
        error = qml_eval(self.widget, page, "errorText")
        self.assertIn("boom", str(error), f"expected 'boom' in errorText, got '{error}'")
        start_calls = [c for c in self.fake.calls if isinstance(c, tuple) and c[0] == "start_profile"]
        names = sorted(c[1] for c in start_calls)
        self.assertEqual(names, ["B", "C"], f"expected B and C attempted, got {names}")
        self.fake_backend._profiles_override = None
        # C never exists in FakeManager.profiles (override-only), so guard.
        c = self.fake.profiles.get("C")
        if c is not None:
            c["status"] = "stopped"
            c["pid"] = None
        # Drop the stale [A,B,C] overview from the shared page so later tests
        # in this class (pytest runs unittest methods alphabetically) read the
        # restored [A,B] state.
        qml_eval(self.widget, page, "refreshNow()")
        pump(self.widget)

    def test_empty_hidden_and_noop(self):
        """With zero profiles the button is hidden and toggleStartAll is a no-op."""
        empty_fake = FakeManager([])
        empty_backend = FakeDashboardBackend(
            empty_fake,
            profiles=[],
            services=[],
            orders={"scheduled_trades": 0, "scheduled_closes": 0, "pending_partials": 0, "total": 0},
            logs={"lines": [], "truncated": False, "requested": 200, "latest_log": None},
        )
        app2, widget2 = create_engine(profile_manager=empty_fake, dashboard_backend=empty_backend)
        app2.processEvents()
        root2 = widget2.rootObject()
        widget2.app = app2
        click_nav(widget2, root2, "Dashboard")
        app2.processEvents()
        page2 = get_page(widget2, root2)
        btn = find_qml_object(page2, "startAllBtn")
        self.assertIsNotNone(btn, "startAllBtn not found")
        self.assertFalse(bool(btn.isVisible()), "startAllBtn should be hidden with 0 profiles")
        qml_eval(widget2, page2, "toggleStartAll()")
        pump(widget2)
        start_calls = [c for c in empty_fake.calls if isinstance(c, tuple) and c[0] == "start_profile"]
        self.assertEqual(len(start_calls), 0, "toggleStartAll must be a no-op with 0 profiles")


if __name__ == "__main__":
    unittest.main()
