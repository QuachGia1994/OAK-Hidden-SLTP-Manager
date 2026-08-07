"""Regression tests for the lightweight NativeQt EN/VN translator."""

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import oak_qt_shell as shell_mod  # noqa: E402
from oak_qt_shell import native_format, native_text, set_native_language


class NativeQtI18nTests(unittest.TestCase):
    def tearDown(self) -> None:
        set_native_language("EN")

    def test_vietnamese_translates_shared_controls(self) -> None:
        set_native_language("VN")

        self.assertEqual(native_text("Dashboard"), "Bảng điều khiển")
        self.assertEqual(native_text("Start selected"), "Chạy profile đã chọn")
        self.assertEqual(native_text("PROFILE NAME"), "TÊN HỒ SƠ")
        self.assertEqual(native_format("Visible SL/TP {state}", state="ON"), "Hiện SL/TP: BẬT")
        self.assertEqual(native_text("Exact profile match"), "Khớp hồ sơ chính xác")
        self.assertEqual(native_format("Total tasks: {count}", count=3), "Tổng tác vụ: 3")
        self.assertEqual(native_text("VN30 Advisor"), "Bộ lọc CP")
        self.assertEqual(native_text("Signals"), "Tín hiệu")
        self.assertEqual(native_text("Pending"), "Lệnh chờ")

    def test_english_and_unknown_values_are_preserved(self) -> None:
        set_native_language("EN")

        self.assertEqual(native_text("Dashboard"), "Dashboard")
        self.assertEqual(native_text("VantageDemo"), "VantageDemo")
        self.assertEqual(native_text("Signals"), "Account Tracking")

    def test_template_translation_preserves_runtime_data(self) -> None:
        set_native_language("VN")

        self.assertEqual(
            native_format("Selected profile: {profile} · Native Qt/QSS, no Chromium", profile="Vantage"),
            "Hồ sơ đang chọn: Vantage · Native Qt/QSS, không Chromium",
        )

    def test_invalid_language_falls_back_to_english(self) -> None:
        set_native_language("system")

        self.assertEqual(native_text("Settings"), "Settings")

    def test_vn_toggle_text_in_rail(self) -> None:
        """Rail profile toggle must show VN translation after rebuild."""
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
                self.assertIn("Chạy profile đã chọn", shell.rail_profile_toggle.text())
            finally:
                shell_mod.set_native_language(prev_lang)
                shell.shutdown()
                shell.window.close()
        finally:
            shell_mod.write_json_atomic(shell_mod.SETTINGS_FILE, prev_settings)


if __name__ == "__main__":
    unittest.main()
