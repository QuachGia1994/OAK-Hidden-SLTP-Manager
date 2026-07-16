# -*- coding: utf-8 -*-
"""Tests for NativeQt diagnostics helper logic."""
from pathlib import Path
import tempfile
import unittest

from oak_qt_shell import filter_log_text, log_line_matches_level, write_bytes_atomic


class TestNativeQtDiagnosticsHelpers(unittest.TestCase):
    def test_log_level_matching_is_coarse_but_predictable(self):
        self.assertTrue(log_line_matches_level("[ERROR] failed to connect", "ERROR"))
        self.assertTrue(log_line_matches_level("WARNING retry soon", "WARN"))
        self.assertTrue(log_line_matches_level("[OK] Connected", "INFO"))
        self.assertFalse(log_line_matches_level("plain heartbeat", "ERROR"))

    def test_filter_log_text_applies_query_and_level(self):
        text = "\n".join(
            [
                "[INFO] Vantage connected",
                "[WARN] Vantage retry",
                "[ERROR] Darwinex failed",
            ]
        )
        self.assertEqual(filter_log_text(text, "vantage", "WARN"), "[WARN] Vantage retry")
        self.assertEqual(filter_log_text(text, "darwinex", "ERROR"), "[ERROR] Darwinex failed")

    def test_write_bytes_atomic_replaces_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bundle.zip"
            write_bytes_atomic(path, b"first")
            write_bytes_atomic(path, b"second")
            self.assertEqual(path.read_bytes(), b"second")
            self.assertFalse(path.with_suffix(".zip.tmp").exists())


if __name__ == "__main__":
    unittest.main()
