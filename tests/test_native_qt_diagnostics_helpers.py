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


class DummyWidget:
    def setPlainText(self, text: str) -> None:
        pass


class DummyLayout:
    def count(self) -> int:
        return 0

    def addWidget(self, widget: Any) -> None:
        pass

    def addStretch(self, stretch: int = 0) -> None:
        pass


class TestDiagnosticsAndCopyPageDeferral(unittest.TestCase):
    """Tests for Diagnostics and Copy Trading page deferral on hidden tabs."""

    def test_refresh_diagnostics_page_skips_when_hidden_unless_forced(self) -> None:
        import oak_qt_shell
        from unittest.mock import MagicMock

        shell = MagicMock(spec=oak_qt_shell.NativeShell)
        shell.diag_summary = DummyWidget()
        shell.diag_log = DummyWidget()
        shell.current_tab = "Profiles"
        shell.profiles = {}
        shell.selected = "Demo"
        shell._latest_log_path.return_value = None
        shell._tail_text.return_value = ""
        shell._artifact_summary.return_value = []
        shell._set_diag_status = MagicMock()
        shell.diag_filter = None
        shell.diag_level = None

        # Without force when hidden: skips log reading
        oak_qt_shell.NativeShell._refresh_diagnostics_page(shell, force=False)
        shell._latest_log_path.assert_not_called()

        # With force=True when hidden: reads log
        oak_qt_shell.NativeShell._refresh_diagnostics_page(shell, force=True)
        shell._latest_log_path.assert_called_once()

    def test_refresh_copy_page_skips_when_hidden_unless_forced(self) -> None:
        import oak_qt_shell
        from unittest.mock import MagicMock

        shell = MagicMock(spec=oak_qt_shell.NativeShell)
        shell.copy_detail = DummyWidget()
        shell.copy_guardrails_layout = DummyLayout()
        shell.current_tab = "Profiles"
        shell.selected = "Demo"
        shell.profiles = {}
        shell._copy_detail_text.return_value = ""

        # Without force when hidden: skips layout rebuild
        oak_qt_shell.NativeShell._refresh_copy_page(shell, force=False)
        shell._copy_detail_text.assert_not_called()

        # With force=True when hidden: executes layout rebuild
        oak_qt_shell.NativeShell._refresh_copy_page(shell, force=True)
        shell._copy_detail_text.assert_called_once()

    def test_switch_tab_forces_refresh_for_diagnostics_and_copy(self) -> None:
        import oak_qt_shell
        from unittest.mock import MagicMock

        shell = MagicMock(spec=oak_qt_shell.NativeShell)
        shell.tab_pages = {"Diagnostics": DummyWidget(), "Copy Trading": DummyWidget(), "Profiles": DummyWidget()}
        shell.stack = MagicMock()
        shell._refresh_nav = MagicMock()
        shell._fade_in_page = MagicMock()
        shell._refresh_diagnostics_page = MagicMock()
        shell._refresh_copy_page = MagicMock()

        # Switch to Diagnostics
        oak_qt_shell.NativeShell.switch_tab(shell, "Diagnostics")
        shell._refresh_diagnostics_page.assert_called_once_with(force=True)

        # Switch to Copy Trading
        oak_qt_shell.NativeShell.switch_tab(shell, "Copy Trading")
        shell._refresh_copy_page.assert_called_once_with(force=True)


if __name__ == "__main__":
    unittest.main()
