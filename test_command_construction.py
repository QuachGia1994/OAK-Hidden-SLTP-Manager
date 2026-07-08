# -*- coding: utf-8 -*-
"""Tests for command construction in dev vs frozen mode.

These tests call the real build_signal_process_cmd() helper (shared by
OAK_Hidden_SLTP_Manager.start_signal_process and this test file) instead of
re-building a fake command inline, so a regression like "dev mode forgets
--profile" is actually caught.
"""
import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils import build_signal_process_cmd, UnsupportedFrozenProcessError


class TestCommandConstruction(unittest.TestCase):
    """Test signal bot command construction for dev and frozen modes."""

    def test_dev_mode_signal_bot_includes_profile(self):
        """Dev mode: signal_bot must receive --profile <profile>."""
        cmd = build_signal_process_cmd(
            "signal_bot", "VantageDemo", frozen=False, executable=sys.executable
        )
        self.assertEqual(
            cmd, [sys.executable, "-u", "mt5_signal_bot.py", "--profile", "VantageDemo"]
        )

    def test_dev_mode_signal_bot_no_profile_selected(self):
        """Dev mode: no profile selected -> no --profile flag appended."""
        cmd = build_signal_process_cmd(
            "signal_bot", "", frozen=False, executable=sys.executable
        )
        self.assertEqual(cmd, [sys.executable, "-u", "mt5_signal_bot.py"])
        self.assertNotIn("--profile", cmd)

    def test_frozen_mode_uses_signal_bot_flag(self):
        """Frozen mode: uses sys.executable --signal-bot --profile X."""
        cmd = build_signal_process_cmd(
            "signal_bot", "VantageDemo", frozen=True, executable=sys.executable
        )
        self.assertEqual(cmd, [sys.executable, "--signal-bot", "--profile", "VantageDemo"])
        self.assertFalse(any(".py" in arg for arg in cmd))

    def test_frozen_mode_no_profile(self):
        """Frozen mode without profile: uses sys.executable --signal-bot."""
        cmd = build_signal_process_cmd(
            "signal_bot", "", frozen=True, executable=sys.executable
        )
        self.assertEqual(cmd, [sys.executable, "--signal-bot"])

    def test_dev_mode_other_processes_no_profile_flag(self):
        """Dev mode: non-signal_bot processes never get --profile."""
        cmd = build_signal_process_cmd(
            "mt_server", "VantageDemo", frozen=False, executable=sys.executable
        )
        self.assertEqual(cmd, [sys.executable, "-u", "mt4_mt5_server.py"])
        self.assertNotIn("--profile", cmd)

    def test_frozen_mode_only_signal_bot_supported(self):
        """Frozen mode: only signal_bot is supported, others raise."""
        for key in ("mt_server", "mimo_bot", "mimo_worker"):
            with self.assertRaises(UnsupportedFrozenProcessError):
                build_signal_process_cmd(
                    key, "VantageDemo", frozen=True, executable=sys.executable
                )


if __name__ == "__main__":
    unittest.main()
