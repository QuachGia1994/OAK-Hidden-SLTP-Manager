# -*- coding: utf-8 -*-
"""Tests for signal bot profile selection.

Covers both CLI arg parsing and the real resolve_active_profile() logic
used by mt5_signal_bot.main(), so a regression in migration-skipping or
missing validation is actually caught (not just argparse behavior).
"""
import unittest
import sys
import os
import json
import tempfile
from unittest.mock import patch

import mt5_signal_bot
from mt5_signal_bot import resolve_active_profile


class TestSignalBotCLIParsing(unittest.TestCase):
    """Test --profile CLI arg parsing."""

    def test_profile_arg_parsing(self):
        """CLI --profile arg is parsed correctly."""
        orig_argv = sys.argv
        try:
            sys.argv = ["mt5_signal_bot.py", "--profile", "VantageDemo"]
            import argparse
            parser = argparse.ArgumentParser()
            parser.add_argument("--profile", type=str, help="Profile name for heartbeat")
            args, _ = parser.parse_known_args()
            self.assertEqual(args.profile, "VantageDemo")
        finally:
            sys.argv = orig_argv

    def test_no_profile_arg_is_none(self):
        """When no --profile arg, parsed value is None."""
        orig_argv = sys.argv
        try:
            sys.argv = ["mt5_signal_bot.py"]
            import argparse
            parser = argparse.ArgumentParser()
            parser.add_argument("--profile", type=str, help="Profile name for heartbeat")
            args, _ = parser.parse_known_args()
            self.assertIsNone(args.profile)
        finally:
            sys.argv = orig_argv


class TestResolveActiveProfile(unittest.TestCase):
    """Test resolve_active_profile(), the real function main() relies on."""

    def _write_profiles(self, data):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        return path

    @patch.object(mt5_signal_bot, "migrate_plaintext_tokens")
    def test_cli_profile_used_when_valid(self, mock_migrate):
        """CLI profile that exists in profiles.json is used as-is."""
        path = self._write_profiles({"VantageDemo": {}, "Other": {}})
        result = resolve_active_profile("VantageDemo", profiles_path=path)
        self.assertEqual(result, "VantageDemo")
        mock_migrate.assert_called_once()

    @patch.object(mt5_signal_bot, "migrate_plaintext_tokens")
    def test_cli_profile_invalid_falls_back_to_first(self, mock_migrate):
        """CLI profile not present in profiles.json warns and falls back."""
        path = self._write_profiles({"RealProfile": {}})
        result = resolve_active_profile("DoesNotExist", profiles_path=path)
        self.assertEqual(result, "RealProfile")

    @patch.object(mt5_signal_bot, "migrate_plaintext_tokens")
    def test_no_cli_profile_uses_first(self, mock_migrate):
        """No CLI profile falls back to first profile in profiles.json."""
        path = self._write_profiles({"FirstProfile": {}, "SecondProfile": {}})
        result = resolve_active_profile(None, profiles_path=path)
        self.assertEqual(result, "FirstProfile")
        mock_migrate.assert_called_once()

    @patch.object(mt5_signal_bot, "migrate_plaintext_tokens")
    def test_migration_runs_even_when_cli_profile_given(self, mock_migrate):
        """Migration must run even when --profile is passed (not just the else branch)."""
        path = self._write_profiles({"VantageDemo": {}})
        resolve_active_profile("VantageDemo", profiles_path=path)
        mock_migrate.assert_called_once()

    def test_missing_profiles_file_returns_empty_string(self):
        """No profiles.json at all -> empty active profile, no crash."""
        result = resolve_active_profile(None, profiles_path="/nonexistent/profiles.json")
        self.assertEqual(result, "")

    def test_missing_profiles_file_with_cli_profile_uses_cli_value(self):
        """No profiles.json but CLI profile given -> trust the CLI value."""
        result = resolve_active_profile("VantageDemo", profiles_path="/nonexistent/profiles.json")
        self.assertEqual(result, "VantageDemo")


if __name__ == "__main__":
    unittest.main()
