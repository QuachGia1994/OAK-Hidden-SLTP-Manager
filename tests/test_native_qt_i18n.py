"""Regression tests for the lightweight NativeQt EN/VN translator."""

import unittest

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
        self.assertEqual(native_text("VN30 Advisor"), "Bộ lọc Cổ phiếu")
        self.assertEqual(native_text("Signals"), "Theo dõi tài khoản")

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


if __name__ == "__main__":
    unittest.main()
