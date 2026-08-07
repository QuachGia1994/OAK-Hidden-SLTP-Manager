"""Visual token contracts for the lightweight NativeQt shell (Tauri parity)."""

import unittest

from oak_qt_shell import app_qss


class NativeQtThemeTests(unittest.TestCase):
    def test_dark_theme_accent_and_bloom(self) -> None:
        stylesheet = app_qss("dark")

        self.assertIn("#2fa572", stylesheet)
        self.assertIn("#0b0f14", stylesheet)
        self.assertIn("rgba(47,165,114,0.13)", stylesheet)

    def test_light_theme_is_distinct_from_dark(self) -> None:
        light = app_qss("light")
        dark = app_qss("dark")

        self.assertIn("#eef1f5", light)
        self.assertIn("#147a52", light)
        self.assertNotIn("#eef1f5", dark)

    def test_contrast_theme_uses_green_accent(self) -> None:
        contrast = app_qss("contrast")

        self.assertIn("#00e676", contrast)
        self.assertIn("#000000", contrast)

    def test_deep_sea_theme_uses_cyan_accent(self) -> None:
        deep_sea = app_qss("deep-sea")

        self.assertIn("#18d6ff", deep_sea)
        self.assertIn("#031016", deep_sea)

    def test_theme_accent_tokens_match_tauri(self) -> None:
        self.assertIn('QLabel[accent="theme"]{color:#2fa572}', app_qss("dark"))
        self.assertIn('QLabel[accent="theme"]{color:#147a52}', app_qss("light"))
        self.assertIn('QLabel[accent="theme"]{color:#18d6ff}', app_qss("deep-sea"))
        self.assertIn('QLabel[accent="theme"]{color:#00e676}', app_qss("contrast"))

    def test_deep_sea_active_row_uses_cyan(self) -> None:
        self.assertIn(
            'QFrame[role="row"][active="true"]{border:1px solid #18d6ff;background:rgba(24,214,255,.07)}',
            app_qss("deep-sea"),
        )

    def test_all_themes_have_compact_padding(self) -> None:
        for theme in ("dark", "light", "deep-sea", "contrast"):
            stylesheet = app_qss(theme)
            self.assertIn('QPushButton[compact="true"]{padding:4px 10px}', stylesheet)

    def test_dark_theme_progressbar_chunk(self) -> None:
        stylesheet = app_qss("dark")
        self.assertIn("QProgressBar::chunk{background:#2fa572", stylesheet)

    def test_unknown_theme_falls_back_to_dark(self) -> None:
        fallback = app_qss("nonexistent_theme")
        dark = app_qss("dark")
        self.assertEqual(fallback, dark)


if __name__ == "__main__":
    unittest.main()
