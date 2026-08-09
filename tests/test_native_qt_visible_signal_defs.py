"""NativeQt no longer exposes the removed MT4 feed service."""
import unittest
from pathlib import Path

import oak_qt_shell


class NativeQtVisibleSignalDefsTests(unittest.TestCase):
    def test_native_shell_has_no_mt4_service_surface(self):
        source = Path(oak_qt_shell.__file__).read_text(encoding="utf-8")
        self.assertNotIn("mt4_feed_server", source)
        self.assertNotIn("_legacy_mt4_feed_enabled", source)
        self.assertNotIn("MT4FeedHealth", source)

    def test_native_shell_retains_mt5_signal_runtime(self):
        source = Path(oak_qt_shell.__file__).read_text(encoding="utf-8")
        self.assertIn("mt5_signal_bot", source)


if __name__ == "__main__":
    unittest.main()
