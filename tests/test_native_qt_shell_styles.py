"""Visual regression tests for the NativeQt shell redesign (Tauri parity)."""

import os
import sys
import time
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import oak_qt_shell as shell_mod  # noqa: E402

THEMES = {
    "dark": "#0b0f14",
    "light": "#eef1f5",
    "deep-sea": "#031016",
    "contrast": "#000000",
}
ACCENTS = {
    "dark": "#2fa572",
    "light": "#147a52",
    "deep-sea": "#18d6ff",
    "contrast": "#00e676",
}


def _close_shell(shell, app):
    """Fully release the process-wide QApplication after a Qt test."""
    shell.shutdown()
    shell.window.close()
    shell = None
    app.processEvents()
    app.shutdown()
    return None


class NativeQtShellStyleTokenTests(unittest.TestCase):
    """Verify app_qss() returns correct tokens for all 4 themes."""

    def test_dark_theme_tokens(self) -> None:
        qss = shell_mod.app_qss("dark")
        self.assertIn("#0b0f14", qss)
        self.assertIn("#2fa572", qss)
        self.assertIn("#111820", qss)
        self.assertIn("#1e2937", qss)

    def test_light_theme_tokens(self) -> None:
        qss = shell_mod.app_qss("light")
        self.assertIn("#eef1f5", qss)
        self.assertIn("#147a52", qss)
        self.assertIn("#ffffff", qss)
        self.assertIn("#c3ccd6", qss)

    def test_deep_sea_theme_tokens(self) -> None:
        qss = shell_mod.app_qss("deep-sea")
        self.assertIn("#031016", qss)
        self.assertIn("#18d6ff", qss)
        self.assertIn("#061219", qss)
        self.assertIn("#1b3b45", qss)

    def test_contrast_theme_tokens(self) -> None:
        qss = shell_mod.app_qss("contrast")
        self.assertIn("#000000", qss)
        self.assertIn("#00e676", qss)
        self.assertIn("#0d0d0d", qss)
        self.assertIn("#4d4d4d", qss)

    def test_unknown_theme_falls_back_to_dark(self) -> None:
        fallback = shell_mod.app_qss("nonexistent_theme")
        dark = shell_mod.app_qss("dark")
        self.assertEqual(fallback, dark)

    def test_all_themes_have_status_role(self) -> None:
        for theme in THEMES:
            qss = shell_mod.app_qss(theme)
            self.assertIn('role="status"', qss, f"Missing status pill in {theme}")

    def test_all_themes_have_stat_role(self) -> None:
        for theme in THEMES:
            qss = shell_mod.app_qss(theme)
            self.assertIn('role="stat"', qss, f"Missing stat frame in {theme}")

    def test_all_themes_have_nav_role(self) -> None:
        for theme in THEMES:
            qss = shell_mod.app_qss(theme)
            self.assertIn('role="nav"', qss, f"Missing nav role in {theme}")

    def test_all_themes_have_lang_role(self) -> None:
        for theme in THEMES:
            qss = shell_mod.app_qss(theme)
            self.assertIn('role="lang"', qss, f"Missing lang role in {theme}")

    def test_all_themes_have_prefs_role(self) -> None:
        for theme in THEMES:
            qss = shell_mod.app_qss(theme)
            self.assertIn('role="prefs"', qss, f"Missing prefs role in {theme}")

    def test_all_themes_have_progressbar(self) -> None:
        for theme in THEMES:
            qss = shell_mod.app_qss(theme)
            self.assertIn("QProgressBar", qss, f"Missing QProgressBar in {theme}")
            self.assertIn("QProgressBar::chunk", qss, f"Missing QProgressBar::chunk in {theme}")

    @unittest.skipUnless(
        os.environ.get("QT_QPA_PLATFORM") == "offscreen",
        "QT_QPA_PLATFORM must be offscreen for parametrized token test",
    )
    def test_parametrized_theme_tokens(self) -> None:
        for theme, expect_bg in THEMES.items():
            expect_accent = ACCENTS[theme]
            qss = shell_mod.app_qss(theme)
            self.assertIn(expect_bg, qss, f"Missing bg {expect_bg} in {theme}")
            self.assertIn(expect_accent, qss, f"Missing accent {expect_accent} in {theme}")


class NativeQtShellRailTests(unittest.TestCase):
    """Verify the restructured rail has all required sections."""

    def tearDown(self) -> None:
        shell_mod.set_native_language("EN")

    def test_rail_builds_without_error(self) -> None:
        try:
            import PySide6  # noqa: F401
        except ImportError:
            self.skipTest("PySide6 not installed")
        qt, err = shell_mod.load_qt()
        self.assertIsNotNone(qt, err)
        shell_mod.QT = qt
        app = qt.QApplication.instance() or qt.QApplication([])
        shell = shell_mod.NativeShell()
        # Verify nav_buttons keys are preserved
        expected_keys = {
            "Dashboard", "Signals", "VN30 Advisor", "Profiles",
            "Copy", "Pending", "Diagnostics", "Settings",
        }
        self.assertEqual(set(shell.nav_buttons.keys()), expected_keys)
        # Verify new attributes exist
        self.assertIsNotNone(shell.rail_lang_en)
        self.assertIsNotNone(shell.rail_lang_vn)
        self.assertIsNotNone(shell.rail_theme_btn)
        self.assertIsNotNone(shell.classic_btn)
        self.assertIsNotNone(shell.hero_status)
        self.assertIsNotNone(shell.rail_profile_toggle)
        self.assertIsNotNone(shell.rail_profile_status)
        self.assertIsNotNone(shell.rail_scroll)
        self.assertEqual(shell.live_timer.interval(), 1000)
        # Verify nav buttons have role="nav"
        for name, btn in shell.nav_buttons.items():
            self.assertEqual(btn.property("role"), "nav", f"{name} missing role=nav")
        # Verify lang buttons have role="lang"
        self.assertEqual(shell.rail_lang_en.property("role"), "lang")
        self.assertEqual(shell.rail_lang_vn.property("role"), "lang")
        # Verify theme button has role="prefs"
        self.assertEqual(shell.rail_theme_btn.property("role"), "prefs")
        shell = _close_shell(shell, app)

    def test_vn_nav_buttons_translate(self) -> None:
        """VN mode must show translated nav labels (icon prefix must not break lookup)."""
        try:
            import PySide6  # noqa: F401
        except ImportError:
            self.skipTest("PySide6 not installed")
        qt, err = shell_mod.load_qt()
        self.assertIsNotNone(qt, err)
        shell_mod.QT = qt
        app = qt.QApplication.instance() or qt.QApplication([])
        # Persist lang=VN to disk so refresh() inside _rebuild_translated_ui
        # doesn't detect a mismatch and reset to EN.
        prev_settings = shell_mod.read_json(shell_mod.SETTINGS_FILE, {})
        vn_settings = {**prev_settings, "lang": "VN"}
        shell_mod.write_json_atomic(shell_mod.SETTINGS_FILE, vn_settings)
        try:
            shell = shell_mod.NativeShell()
            prev_lang = shell_mod.NATIVE_LANGUAGE
            try:
                shell_mod.set_native_language("VN")
                shell.settings = {**shell.settings, "lang": "VN"}
                shell._rebuild_translated_ui()
                expected = {
                    "Dashboard": "Bảng điều khiển",
                    "Signals": "Tín hiệu",
                    "VN30 Advisor": "Bộ lọc CP",
                    "Profiles": "Hồ sơ",
                    "Copy": "Sao chép",
                    "Pending": "Lệnh chờ",
                    "Settings": "Cài đặt",
                }
                for key, vn_label in expected.items():
                    btn = shell.nav_buttons[key]
                    self.assertIn(vn_label, btn.text(), f"VN nav label missing for {key}: {btn.text()!r}")
            finally:
                shell_mod.set_native_language(prev_lang)
                shell = _close_shell(shell, app)
        finally:
            shell_mod.write_json_atomic(shell_mod.SETTINGS_FILE, prev_settings)

    def test_rail_profile_toggle_safe_when_no_selection(self) -> None:
        """Toggle must not launch anything when no valid profile is selected."""
        try:
            import PySide6  # noqa: F401
        except ImportError:
            self.skipTest("PySide6 not installed")
        qt, err = shell_mod.load_qt()
        self.assertIsNotNone(qt, err)
        shell_mod.QT = qt
        app = qt.QApplication.instance() or qt.QApplication([])
        shell = shell_mod.NativeShell()
        shell.selected = ""
        shell._toggle_selected_profile()
        self.assertIn("Select a valid profile", shell.console.toPlainText())
        shell = _close_shell(shell, app)

    def test_rail_toggle_reflects_running_state(self) -> None:
        """Fake running monitor must flip the rail toggle to Stop/Running labels."""
        try:
            import PySide6  # noqa: F401
        except ImportError:
            self.skipTest("PySide6 not installed")
        qt, err = shell_mod.load_qt()
        self.assertIsNotNone(qt, err)
        shell_mod.QT = qt
        app = qt.QApplication.instance() or qt.QApplication([])
        shell_mod.set_native_language("EN")
        shell = shell_mod.NativeShell()
        # Ensure EN regardless of what settings.json contains
        shell_mod.set_native_language("EN")
        shell.settings = {**shell.settings, "lang": "EN"}

        class _FakeProc:
            def state(self):  # noqa: D401
                return 999  # any value != QT.NotRunning counts as running

        shell.monitor_processes = {"FakeProfile": _FakeProc()}
        shell.profiles = {"FakeProfile": {}}
        shell.selected = "FakeProfile"
        shell._refresh_profile_controls()
        self.assertIn("Stop selected", shell.rail_profile_toggle.text())
        self.assertIn("Running", shell.rail_profile_status.text())
        self.assertEqual(shell.rail_profile_toggle.property("intent"), "danger")
        shell = _close_shell(shell, app)


class NativeQtShellFadeTests(unittest.TestCase):
    """Verify the 150ms tab-switch fade exists."""

    def test_fade_in_page_method_exists(self) -> None:
        self.assertTrue(hasattr(shell_mod.NativeShell, "_fade_in_page"))

    def test_switch_tab_calls_fade(self) -> None:
        try:
            import PySide6  # noqa: F401
        except ImportError:
            self.skipTest("PySide6 not installed")
        qt, err = shell_mod.load_qt()
        self.assertIsNotNone(qt, err)
        shell_mod.QT = qt
        app = qt.QApplication.instance() or qt.QApplication([])
        shell = shell_mod.NativeShell()
        # Verify switch_tab does not crash
        shell.switch_tab("Dashboard")
        app.processEvents()
        shell.switch_tab("Signals")
        app.processEvents()
        shell.switch_tab("Settings")
        app.processEvents()
        shell = _close_shell(shell, app)


class NativeQtShellRailFitTests(unittest.TestCase):
    """Nav buttons must render at full height: the rail must never overflow and
    compress rows (previously the redesigned rail needed ~1050px but only had
    ~744px at the default window, squeezing every nav button to ~17px and
    hiding its label)."""

    def test_rail_layout_fits_default_window(self) -> None:
        try:
            import PySide6  # noqa: F401
        except ImportError:
            self.skipTest("PySide6 not installed")
        qt, err = shell_mod.load_qt()
        self.assertIsNotNone(qt, err)
        shell_mod.QT = qt
        app = qt.QApplication.instance() or qt.QApplication([])
        shell = shell_mod.NativeShell()
        shell.window.resize(1240, 760)
        shell.window.show()
        app.processEvents()
        try:
            for name, btn in shell.nav_buttons.items():
                self.assertGreaterEqual(
                    btn.height(),
                    24,
                    f"nav button {name} vertically compressed ({btn.height()}px < 24px): "
                    "rail content overflows the window height",
                )
                self.assertGreaterEqual(
                    btn.width(),
                    btn.sizeHint().width(),
                    f"nav button {name} label clipped: width {btn.width()}px < "
                    f"sizeHint {btn.sizeHint().width()}px",
                )
            self.assertEqual(
                shell.rail_scroll.verticalScrollBar().maximum(),
                0,
                "rail content must fit the default window without a scrollbar",
            )
        finally:
            shell = _close_shell(shell, app)


class NativeQtShellScreenshotTests(unittest.TestCase):
    """Capture screenshots for every theme/tab combination."""

    @unittest.skip("Visual screenshot gate runs separately in tests/run_native_qt_screenshot.py")
    def test_screenshot_capture(self) -> None:
        """The screenshot gate is intentionally isolated from in-process Qt tests."""
        import subprocess

        runner = ROOT / "tests" / "run_native_qt_screenshot.py"
        completed = subprocess.run(
            [sys.executable, str(runner)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(
            completed.returncode,
            0,
            "NativeQt screenshot subprocess failed.\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
