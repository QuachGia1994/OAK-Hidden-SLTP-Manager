"""NativeQt window-icon contracts."""

import unittest

from oak_qt_shell import app_icon_path


class NativeQtIconTests(unittest.TestCase):
    def test_icon_asset_is_resolved_for_the_window_chrome(self) -> None:
        icon = app_icon_path()

        self.assertIsNotNone(icon)
        self.assertEqual(icon.name, "icon.ico")
        self.assertTrue(icon.is_file())


if __name__ == "__main__":
    unittest.main()
