# -*- coding: utf-8 -*-
"""XAU M30 flip: H=2-4 rebuild GBP from final XAU; H=5+ XAU only."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import mt5_signal_bot
from mt5_signal_bot import apply_xauusd_m30_logic, get_pair_direction


def _dt_monday():
    return datetime(2026, 7, 6, 4, 45, tzinfo=timezone.utc)  # Monday


class TestApplyXauusdM30Rebuild(unittest.TestCase):
    def test_h3_after_flip_gbpaud_opposite_gbpjpy_same(self):
        """H=2-4: pairs relative to final XAU after flip."""
        dt = _dt_monday()
        H = 3
        sig = "BUY"
        pair_dirs = get_pair_direction(H, sig, dt)
        self.assertEqual(pair_dirs["XAUUSD"], "BUY")
        self.assertEqual(pair_dirs["GBPAUD"], "SELL")
        self.assertEqual(pair_dirs["GBPJPY"], "BUY")

        with patch.object(mt5_signal_bot, "get_xauusd_m30_signal", return_value="BUY"):
            apply_xauusd_m30_logic(pair_dirs, sig, dt, H)

        self.assertEqual(pair_dirs["XAUUSD"], "SELL")
        self.assertEqual(pair_dirs["GBPAUD"], "BUY")
        self.assertEqual(pair_dirs["GBPJPY"], "SELL")
        self.assertEqual(pair_dirs["GBPUSD"], "--")
        self.assertEqual(pair_dirs["GBPCAD"], "--")

    def test_h5_xau_only_after_flip(self):
        """H=5-8: Focus only — no GBP in pair_dirs even after M30 flip."""
        dt = _dt_monday()
        for H in (5, 6, 7, 8):
            with self.subTest(H=H):
                sig = "SELL"
                pair_dirs = get_pair_direction(H, sig, dt)
                self.assertEqual(pair_dirs, {"XAUUSD": "SELL"})
                with patch.object(mt5_signal_bot, "get_xauusd_m30_signal", return_value="SELL"):
                    apply_xauusd_m30_logic(pair_dirs, sig, dt, H)
                self.assertEqual(pair_dirs["XAUUSD"], "BUY")
                for p in ("GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"):
                    self.assertNotIn(p, pair_dirs)

    def test_h9_plus_xau_only_after_flip(self):
        dt = _dt_monday()
        for H in (9, 11, 12, 15):
            with self.subTest(H=H):
                sig = "BUY"
                pair_dirs = get_pair_direction(H, sig, dt)
                self.assertEqual(pair_dirs, {"XAUUSD": "BUY"})
                with patch.object(mt5_signal_bot, "get_xauusd_m30_signal", return_value="BUY"):
                    apply_xauusd_m30_logic(pair_dirs, sig, dt, H)
                self.assertEqual(pair_dirs["XAUUSD"], "SELL")
                for p in ("GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"):
                    self.assertNotIn(p, pair_dirs)


if __name__ == "__main__":
    unittest.main()
