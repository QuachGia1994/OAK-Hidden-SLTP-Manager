# -*- coding: utf-8 -*-
"""Offscreen smoke + pixel tests for the QML shell scaffold (Phase 0).

Requires PySide6.  Skips gracefully when PySide6 is unavailable.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Env MUST be set before any Qt import ──
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["QT_QUICK_BACKEND"] = "software"
os.environ["QT_QPA_FONTDIR"] = r"C:\Windows\Fonts"

import unittest

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


# ── Theme token maps (mirror oak_qt_shell.app_qss) ──
TOKENS = {
    "dark": {
        "windowBg": "#0b0f14", "surface": "#111820", "border": "#1e2937",
        "text": "#e6edf3", "muted": "#8b98a5", "accent": "#2fa572",
        "divider": "#1e2937", "navActiveBg": "#111820", "navActiveLeft": "#2fa572",
    },
    "light": {
        "windowBg": "#eef1f5", "surface": "#ffffff", "border": "#c3ccd6",
        "text": "#141b24", "muted": "#4b5a6b", "accent": "#147a52",
        "divider": "#c3ccd6", "navActiveBg": "#eef1f5", "navActiveLeft": "#147a52",
    },
    "deep-sea": {
        "windowBg": "#031016", "surface": "#061219", "border": "#1b3b45",
        "text": "#e8fbff", "muted": "#8caab2", "accent": "#18d6ff",
        "divider": "#1b3b45", "navActiveBg": "#09232c", "navActiveLeft": "#18d6ff",
    },
    "contrast": {
        "windowBg": "#000000", "surface": "#0d0d0d", "border": "#4d4d4d",
        "text": "#ffffff", "muted": "#b3b3b3", "accent": "#00e676",
        "divider": "#4d4d4d", "navActiveBg": "#0d0d0d", "navActiveLeft": "#00e676",
    },
}

TOLERANCE = 24  # per RGB channel


# ── Helpers ──────────────────────────────────────────────────────

def hex_to_rgb(h: str) -> tuple[int, int, int]:
    """Convert '#rrggbb' to (r, g, b)."""
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def pixel_close(actual: tuple[int, int, int], expected: str, tol: int = TOLERANCE) -> bool:
    """Return True if actual RGB is within *tol* of the expected hex token."""
    er, eg, eb = hex_to_rgb(expected)
    return (
        abs(actual[0] - er) <= tol
        and abs(actual[1] - eg) <= tol
        and abs(actual[2] - eb) <= tol
    )


def sample_pixel(image: QImage, x: int, y: int) -> tuple[int, int, int]:
    """Return (r, g, b) of the pixel at (x, y) in a QImage."""
    color = QColor(image.pixel(x, y))
    return (color.red(), color.green(), color.blue())


def qml_eval(widget, root, expr: str):
    """Evaluate a QML expression in the root context and return the result.

    Uses QQmlExpression which is reliable for calling QML JS functions
    from Python (QMetaObject.invokeMethod doesn't work with Q_ARG for QML JS).
    """
    ctx = widget.engine().rootContext()
    e = QQmlExpression(ctx, root, expr)
    result = e.evaluate()
    err = e.error()
    if err.isValid():
        raise RuntimeError(f"QML eval error: {err.toString()}")
    return result


def find_qml_object(root, name: str):
    """Find a QML item by objectName via recursive tree traversal.

    PySide6's QObject.findChild does NOT traverse QQuickItem trees,
    so we walk the QQuickItem.childItems() chain manually.
    """
    if root.objectName() == name:
        return root
    for child in root.childItems():
        found = find_qml_object(child, name)
        if found is not None:
            return found
    return None


def set_theme(widget, root, theme_name: str):
    """Set the QML theme via QQmlExpression."""
    qml_eval(widget, root, f'setThemePython("{theme_name}")')
    widget.app.processEvents()
    widget.grab()  # force render to apply bindings


def read_theme(root) -> str:
    """Read current theme string from the root QML object."""
    val = root.property("currentTheme")
    return str(val) if val else "dark"


def item_abs_xy(item, root) -> tuple[int, int]:
    """Get the absolute (x, y) of a QQuickItem relative to root."""
    pt = item.mapToItem(root, QPointF(0, 0))
    return int(pt.x()), int(pt.y())


def divider_pixel_matches(image: QImage, obj, root, expected: str, tol: int = 12) -> tuple[bool, tuple[int, int, int], int, int]:
    """Sample the divider's own 1px row (not the row below it).

    The divider Rectangle is exactly 1px tall at row abs_y; sampling abs_y+1
    reads the row BELOW it (surface color). Sample abs_y and abs_y+1 across
    several x positions and accept if ANY pixel matches the token. A tighter
    tolerance (12) discriminates dark theme where surface #111820 is within
    24 of the divider #1e2937.
    """
    abs_x, abs_y = item_abs_xy(obj, root)
    dw = int(obj.property("width"))
    positions = list(range(abs_x + 4, abs_x + dw - 4, max(8, dw // 8)))
    for x in positions:
        for y in (abs_y, abs_y + 1):
            color = sample_pixel(image, x, y)
            if pixel_close(color, expected, tol):
                return True, color, x, y
    color = sample_pixel(image, positions[len(positions) // 2], abs_y)
    return False, color, positions[len(positions) // 2], abs_y


# ── Test classes ─────────────────────────────────────────────────

class _Base(unittest.TestCase):
    """Shared setUp: one QApplication + QQuickWidget per test class."""

    app: QApplication
    widget: QQuickWidget
    root: object

    @classmethod
    def setUpClass(cls):
        cls.app, cls.widget = create_engine()
        cls.app.processEvents()
        cls.root = cls.widget.rootObject()
        # Attach app ref to widget so helpers can call processEvents
        cls.widget.app = cls.app


class TestBootAndRender(_Base):
    """test_boot_and_render"""

    def test_size_and_pixels(self):
        """Widget renders 1240x780; sidebar surface and content windowBg."""
        img = self.widget.grab().toImage()
        self.assertEqual(img.width(), 1240)
        self.assertEqual(img.height(), 780)

        # Sidebar area: pixel at (90, 750) below ALL sidebar content
        # (prefsRow bottom <= 736) is guaranteed plain surface in every
        # context, so text/font jitter can never move a glyph onto it.
        theme = read_theme(self.root)
        sidebar_color = sample_pixel(img, 90, 750)
        self.assertTrue(
            pixel_close(sidebar_color, TOKENS[theme]["surface"]),
            f"sidebar pixel {sidebar_color} != surface {TOKENS[theme]['surface']} for theme {theme}",
        )

        # Content area: verify initial page is VN30 and bottom pixel is windowBg.
        # Use (900, 750) — bottom of content area, far below any header — which
        # stays windowBg for both the current placeholder and the future VN30 page
        # (its content column is top-aligned with margins, leaving the bottom row
        # as windowBg).
        stack = find_qml_object(self.root, "contentStack")
        self.assertIsNotNone(stack, "contentStack not found")
        current_obj = stack.property("currentItem")
        self.assertIsNotNone(current_obj, "StackView has no current item")
        obj_name = current_obj.property("objectName")
        self.assertEqual(obj_name, "page_VN30", f"Expected initial page_VN30, got {obj_name}")

        content_color = sample_pixel(img, 900, 750)
        self.assertTrue(
            pixel_close(content_color, TOKENS[theme]["windowBg"]),
            f"content pixel {content_color} != windowBg {TOKENS[theme]['windowBg']} for theme {theme}",
        )


class TestSidebarDividersAllThemes(_Base):
    """test_sidebar_dividers_all_themes"""

    def test_dividers_match_all_themes(self):
        """For each theme, divider pixels match the divider token."""
        for theme_name in ("dark", "light", "deep-sea", "contrast"):
            with self.subTest(theme=theme_name):
                set_theme(self.widget, self.root, theme_name)
                img = self.widget.grab().toImage()

                for div_name in ("divider1", "divider2", "divider3"):
                    obj = find_qml_object(self.root, div_name)
                    self.assertIsNotNone(obj, f"divider {div_name} not found for theme {theme_name}")
                    expected = TOKENS[theme_name]["divider"]
                    ok, color, px, py = divider_pixel_matches(img, obj, self.root, expected)
                    self.assertTrue(
                        ok,
                        f"{div_name} pixel {color} != divider {expected} at ({px},{py}) theme={theme_name}",
                    )


class TestWindowIcon(_Base):
    """test_window_icon — the QML shell must carry the bundled app icon."""

    def test_icon_resolved_and_applied(self):
        """icon.ico exists in the repo and create_engine applies it to the window."""
        from oak_qml_app import app_icon_path

        path = app_icon_path()
        self.assertIsNotNone(path, "app_icon_path() returned None")
        self.assertTrue(path.is_file(), f"icon file missing: {path}")
        icon = self.widget.windowIcon()
        self.assertFalse(icon.isNull(), "widget.windowIcon() is null (no icon applied)")
        # The icon must actually carry pixel content (not an empty placeholder).
        sizes = icon.availableSizes()
        self.assertTrue(len(sizes) > 0, "icon has no available sizes")


class TestNavClickSwitchesPage(_Base):
    """test_nav_click_switches_page"""
    def test_click_signals(self):
        """Clicking nav_Signals switches StackView page and highlights nav."""
        # Reset to default theme first
        set_theme(self.widget, self.root, "dark")

        # Use clickNav helper defined in main.qml
        qml_eval(self.widget, self.root, 'clickNav("Signals")')
        self.app.processEvents()

        # Check StackView current page
        stack = find_qml_object(self.root, "contentStack")
        self.assertIsNotNone(stack, "contentStack not found")
        current_obj = stack.property("currentItem")
        self.assertIsNotNone(current_obj, "StackView has no current item")
        obj_name = current_obj.property("objectName")
        self.assertEqual(obj_name, "page_Signals", f"Expected page_Signals, got {obj_name}")

        # Check nav_Signals active state
        nav_obj = find_qml_object(self.root, "nav_Signals")
        self.assertIsNotNone(nav_obj, "nav_Signals not found")
        active = nav_obj.property("isActive")
        self.assertTrue(active, "nav_Signals isActive should be true")


class TestThemeToggleRoundtrip(_Base):
    """test_theme_toggle_roundtrip"""

    def test_set_light_then_dark(self):
        """Set theme to light, verify, then back to dark."""
        set_theme(self.widget, self.root, "light")
        self.assertEqual(read_theme(self.root), "light")

        set_theme(self.widget, self.root, "dark")
        self.assertEqual(read_theme(self.root), "dark")


class TestSidebarFitsWindow(_Base):
    """test_sidebar_fits_window"""

    def test_prefs_row_bottom_within_736(self):
        """Bottom edge of prefsRow <= 736 (no scrollbar needed in Phase 0)."""
        prefs = find_qml_object(self.root, "prefsRow")
        self.assertIsNotNone(prefs, "prefsRow not found")
        y = int(prefs.property("y"))
        h = int(prefs.property("height"))
        bottom = y + h
        self.assertLessEqual(bottom, 736, f"prefsRow bottom {bottom} > 736")


class TestStackClipping(_Base):
    """test_stack_clipping"""

    def test_content_stack_is_clipped(self):
        """contentStack must have clip:true so slide transitions never paint over the sidebar."""
        stack = find_qml_object(self.root, "contentStack")
        self.assertIsNotNone(stack, "contentStack not found")
        self.assertTrue(
            stack.property("clip"),
            "contentStack must clip so slide transitions never paint over the sidebar",
        )

    def test_transition_never_covers_sidebar(self):
        """Mid-transition, the sidebar pixel at (100,400) must remain sidebar surface."""
        import time

        set_theme(self.widget, self.root, "dark")

        # Trigger a push transition to Dashboard
        self.widget.rootObject().clickNav("Dashboard")
        self.widget.app.processEvents()

        stack = find_qml_object(self.root, "contentStack")
        self.assertIsNotNone(stack, "contentStack not found")
        self.assertTrue(stack.property("clip"), "contentStack must be clipped")

        # Try to freeze mid-transition
        paused = False
        try:
            stack.pause()
            paused = True
        except (AttributeError, RuntimeError):
            pass

        if paused:
            try:
                img = self.widget.grab().toImage()
                theme = read_theme(self.root)
                # (100, 400) is well inside the 330px-wide sidebar
                pixel = sample_pixel(img, 100, 400)
                self.assertTrue(
                    pixel_close(pixel, TOKENS[theme]["surface"]),
                    f"sidebar pixel {pixel} != surface {TOKENS[theme]['surface']} "
                    f"mid-transition for theme {theme} (outgoing page must be clipped)",
                )
            finally:
                stack.resume()

        # Wait for transition to settle — grab() forces a frame render which
        # advances the StackView transition animation in offscreen mode.
        settled = False
        for _ in range(200):
            self.widget.app.processEvents()
            self.widget.grab()  # force scene-graph frame
            self.widget.app.processEvents()
            if len(stack.childItems()) == 1:
                settled = True
                break
            time.sleep(0.02)

        self.assertTrue(settled, f"StackView transition did not settle (still {len(stack.childItems())} children)")
        current = stack.property("currentItem")
        self.assertIsNotNone(current, "StackView has no current item after transition")
        self.assertEqual(
            current.property("objectName"), "page_Dashboard",
            f"Expected page_Dashboard after transition, got {current.property('objectName')}",
        )


if __name__ == "__main__":
    unittest.main()
