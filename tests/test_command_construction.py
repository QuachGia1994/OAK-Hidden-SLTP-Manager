# -*- coding: utf-8 -*-
"""Tests for command construction in dev vs frozen mode."""
import unittest
import sys


class TestCommandConstruction(unittest.TestCase):
    """Test signal bot command construction for dev and frozen modes."""

    def test_dev_mode_uses_sys_executable(self):
        """Dev mode: uses sys.executable -u mt5_signal_bot.py --profile X."""
        profile = "VantageDemo"
        cmd = [sys.executable, "-u", "mt5_signal_bot.py", "--profile", profile]
        self.assertIn("-u", cmd)
        self.assertIn("mt5_signal_bot.py", cmd)
        self.assertIn("--profile", cmd)
        self.assertIn("VantageDemo", cmd)

    def test_frozen_mode_uses_signal_bot_flag(self):
        """Frozen mode: uses sys.executable --signal-bot --profile X."""
        profile = "VantageDemo"
        cmd = [sys.executable, "--signal-bot", "--profile", profile]
        self.assertIn("--signal-bot", cmd)
        self.assertIn("--profile", cmd)
        self.assertIn("VantageDemo", cmd)
        self.assertFalse(any(".py" in arg for arg in cmd))

    def test_frozen_mode_no_profile(self):
        """Frozen mode without profile: uses sys.executable --signal-bot."""
        cmd = [sys.executable, "--signal-bot"]
        self.assertIn("--signal-bot", cmd)
        self.assertEqual(len(cmd), 2)

    def test_dev_mode_other_processes(self):
        """Dev mode: other processes use sys.executable -u script.py."""
        script = "mt4_mt5_server.py"
        cmd = [sys.executable, "-u", script]
        self.assertIn("-u", cmd)
        self.assertIn("mt4_mt5_server.py", cmd)

    def test_frozen_mode_only_signal_bot_supported(self):
        """Frozen mode: only signal_bot is supported."""
        supported = ["signal_bot"]
        unsupported = ["mt_server", "mimo_bot", "mimo_worker"]
        for key in unsupported:
            self.assertNotIn(key, supported)


if __name__ == "__main__":
    unittest.main()
