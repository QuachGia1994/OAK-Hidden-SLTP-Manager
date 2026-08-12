# -*- coding: utf-8 -*-
"""Tests for NativeQt profile editor helper logic."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import oak_qt_shell
from oak_qt_shell import normalize_profile_name, unique_profile_name, write_json_atomic


class TestNativeQtProfileHelpers(unittest.TestCase):
    def test_normalize_profile_name_trims_and_collapses_spaces(self):
        self.assertEqual(normalize_profile_name("  Vantage   Demo  "), "Vantage Demo")

    def test_normalize_profile_name_falls_back(self):
        self.assertEqual(normalize_profile_name("   "), "NewProfile")

    def test_unique_profile_name_adds_compact_suffix(self):
        existing = {"NewProfile", "NewProfile 2", "NewProfile 3"}
        self.assertEqual(unique_profile_name(existing, "NewProfile"), "NewProfile 4")

    def test_write_json_atomic_replaces_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profiles.json"
            write_json_atomic(path, {"A": {"profile_name": "A"}})
            self.assertIn('"A"', path.read_text(encoding="utf-8"))
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_write_json_atomic_uses_shared_json_writer(self):
        path = Path("profiles.json")
        payload = {"A": {"profile_name": "A"}}
        with patch.object(oak_qt_shell, "save_json") as save_mock:
            write_json_atomic(path, payload)

        save_mock.assert_called_once_with(path, payload)


class DummyWidget:
    def setPlainText(self, text: str) -> None:
        pass


class DummyLayout:
    def count(self) -> int:
        return 0

    def parentWidget(self) -> unittest.mock.Any:
        return None

    def addWidget(self, widget: unittest.mock.Any) -> None:
        pass

    def addStretch(self, stretch: int = 0) -> None:
        pass


class TestProfilePageDeferral(unittest.TestCase):
    """Tests for Profile page deferral on hidden tabs."""

    def test_refresh_profile_page_skips_when_hidden_unless_forced(self) -> None:
        from unittest.mock import MagicMock

        shell = MagicMock(spec=oak_qt_shell.NativeShell)
        shell.profile_cards_layout = DummyLayout()
        shell.profile_detail = DummyWidget()
        shell.current_tab = "Pending"
        shell.profiles = {}
        shell._running_profiles.return_value = []

        # Without force when hidden: skips layout rebuild
        oak_qt_shell.NativeShell._refresh_profile_page(shell, force=False)
        shell._profile_detail_text.assert_not_called()

        # With force=True when hidden: executes layout rebuild
        oak_qt_shell.NativeShell._refresh_profile_page(shell, force=True)
        shell._profile_detail_text.assert_called_once()

    def test_switch_tab_forces_refresh_for_profiles(self) -> None:
        from unittest.mock import MagicMock

        shell = MagicMock(spec=oak_qt_shell.NativeShell)
        shell.tab_pages = {"Profiles": DummyWidget(), "Pending": DummyWidget()}
        shell.stack = MagicMock()
        shell._refresh_nav = MagicMock()
        shell._fade_in_page = MagicMock()
        shell._refresh_profile_page = MagicMock()

        # Switch to Profiles
        oak_qt_shell.NativeShell.switch_tab(shell, "Profiles")
        shell._refresh_profile_page.assert_called_once_with(force=True)


if __name__ == "__main__":
    unittest.main()
