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


if __name__ == "__main__":
    unittest.main()
