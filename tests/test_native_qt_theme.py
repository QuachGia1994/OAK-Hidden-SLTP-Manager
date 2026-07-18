"""Visual token contracts for the lightweight NativeQt shell."""

import unittest

from oak_qt_shell import app_qss


class NativeQtThemeTests(unittest.TestCase):
    def test_contrast_uses_amber_navigation_and_red_primary_actions(self) -> None:
        stylesheet = app_qss("contrast")

        self.assertIn("background:#c64339;color:#fffaf6", stylesheet)
        self.assertIn("background:#d69f27;color:#120e05", stylesheet)

    def test_contrast_is_visually_distinct_from_soft_dark(self) -> None:
        contrast = app_qss("contrast")
        dark = app_qss("dark")

        self.assertIn("#Root{background:#020202}", contrast)
        self.assertIn("border-radius:10px", contrast)
        self.assertNotIn("#Root{background:#020202}", dark)

    def test_theme_value_and_combo_selection_follow_each_skin(self) -> None:
        self.assertIn('QLabel[accent="theme"]{color:#20d4a4}', app_qss("dark"))
        self.assertIn('QLabel[accent="theme"]{color:#18d6ff}', app_qss("deep-sea"))
        self.assertIn('QLabel[accent="theme"]{color:#f1c45a}', app_qss("contrast"))
        self.assertIn(
            "QComboBox QAbstractItemView::item:selected{background:#18d6ff;color:#021014}",
            app_qss("deep-sea"),
        )
        self.assertIn(
            'QFrame[role="row"][active="true"]{background:#061a22;border:1px solid #18d6ff}',
            app_qss("deep-sea"),
        )

    def test_buttons_can_shrink_inside_compact_action_rows(self) -> None:
        stylesheet = app_qss("dark")

        self.assertIn("min-width:0", stylesheet)
        self.assertIn("padding:10px 12px", stylesheet)


if __name__ == "__main__":
    unittest.main()
