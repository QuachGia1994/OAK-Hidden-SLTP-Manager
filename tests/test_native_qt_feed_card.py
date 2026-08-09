"""Regression tests for the MT5-only NativeQt runtime surface."""
import unittest
from pathlib import Path

import oak_qt_shell


class NativeQtMT5SurfaceTests(unittest.TestCase):
    def test_native_shell_has_no_legacy_mt4_feed_surface(self):
        source = Path(oak_qt_shell.__file__).read_text(encoding="utf-8")
        self.assertNotIn("mt4_feed_server", source)
        self.assertNotIn("MT4FeedHealth", source)
        self.assertNotIn("format_feed_card_details", source)

    def test_native_shell_uses_mt5_signal_runtime(self):
        source = Path(oak_qt_shell.__file__).read_text(encoding="utf-8")
        self.assertIn("mt5_signal_bot", source)


if __name__ == "__main__":
    unittest.main()
