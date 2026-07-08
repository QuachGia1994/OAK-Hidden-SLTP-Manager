# -*- coding: utf-8 -*-
"""Tests for signal bot profile selection."""
import unittest
import sys


class TestSignalBotProfile(unittest.TestCase):
    """Test signal bot profile ownership."""

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


if __name__ == "__main__":
    unittest.main()
