# -*- coding: utf-8 -*-
"""XAU M30 flip: H=2-8 rebuild GBP from final XAU; H=9+ keep GBP on pattern Signal."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import mt5_signal_bot
from mt5_signal_bot import apply_xauusd_m30_logic, get_pair_direction


def _dt_monday():
    return datetime(2026, 7, 6, 4, 45, tzinfo=timezone.utc)  # Monday


class TestApplyXauusdM30Rebuild(unittest.TestCase):
    def test_h3_after_flip_gbpaud_opposite_gbpjpy_same(self):
        """H=2-8: pairs relative to final XAU after flip."""
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
        self.assertEqual(pair_dirs["GBPAUD"], "BUY")   # opposite final XAU
        self.assertEqual(pair_dirs["GBPJPY"], "SELL")  # same final XAU
        self.assertEqual(pair_dirs["GBPUSD"], "--")
        self.assertEqual(pair_dirs["GBPCAD"], "--")

    def test_h5_after_flip_gbpaud_opposite_gbpjpy_same(self):
        dt = _dt_monday()
        H = 5
        sig = "SELL"
        pair_dirs = get_pair_direction(H, sig, dt)

        with patch.object(mt5_signal_bot, "get_xauusd_m30_signal", return_value="SELL"):
            apply_xauusd_m30_logic(pair_dirs, sig, dt, H)

        self.assertEqual(pair_dirs["XAUUSD"], "BUY")
        self.assertEqual(pair_dirs["GBPAUD"], "SELL")
        self.assertEqual(pair_dirs["GBPJPY"], "BUY")

    def test_h11_gbp_stays_on_pattern_signal_after_xau_flip(self):
        """H=11: Signal BUY → GBPAUD/GBPUSD/GBPJPY SELL, GBPCAD BUY.
        Even if XAU flips to SELL, GBP must NOT invert with XAU."""
        dt = _dt_monday()
        H = 11
        sig = "BUY"
        pair_dirs = get_pair_direction(H, sig, dt)
        self.assertEqual(pair_dirs["XAUUSD"], "BUY")
        self.assertEqual(pair_dirs["GBPAUD"], "SELL")
        self.assertEqual(pair_dirs["GBPUSD"], "SELL")
        self.assertEqual(pair_dirs["GBPJPY"], "SELL")
        self.assertEqual(pair_dirs["GBPCAD"], "BUY")

        with patch.object(mt5_signal_bot, "get_xauusd_m30_signal", return_value="BUY"):
            # same as sig → flip XAU only
            apply_xauusd_m30_logic(pair_dirs, sig, dt, H)

        self.assertEqual(pair_dirs["XAUUSD"], "SELL")  # flipped
        # Still relative to pattern Signal BUY — not to final XAU
        self.assertEqual(pair_dirs["GBPAUD"], "SELL")
        self.assertEqual(pair_dirs["GBPUSD"], "SELL")
        self.assertEqual(pair_dirs["GBPJPY"], "SELL")
        self.assertEqual(pair_dirs["GBPCAD"], "BUY")

    def test_h11_sell_signal_mapping(self):
        dt = _dt_monday()
        pair_dirs = get_pair_direction(11, "SELL", dt)
        self.assertEqual(pair_dirs["XAUUSD"], "SELL")
        self.assertEqual(pair_dirs["GBPAUD"], "BUY")
        self.assertEqual(pair_dirs["GBPUSD"], "BUY")
        self.assertEqual(pair_dirs["GBPJPY"], "BUY")
        self.assertEqual(pair_dirs["GBPCAD"], "SELL")

    def test_h9_gbp_stays_on_signal(self):
        dt = _dt_monday()
        sig = "BUY"
        pair_dirs = get_pair_direction(9, sig, dt)
        with patch.object(mt5_signal_bot, "get_xauusd_m30_signal", return_value="BUY"):
            apply_xauusd_m30_logic(pair_dirs, sig, dt, 9)
        self.assertEqual(pair_dirs["XAUUSD"], "SELL")
        self.assertEqual(pair_dirs["GBPAUD"], "SELL")  # opposite Signal BUY
        self.assertEqual(pair_dirs["GBPUSD"], "BUY")
        self.assertEqual(pair_dirs["GBPJPY"], "BUY")
        self.assertEqual(pair_dirs["GBPCAD"], "BUY")


if __name__ == "__main__":
    unittest.main()
