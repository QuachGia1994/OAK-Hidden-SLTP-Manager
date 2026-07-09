# -*- coding: utf-8 -*-
"""After XAU M30 flip, GBP pairs must rebuild from final XAUUSD (not pattern sig)."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import mt5_signal_bot
from mt5_signal_bot import apply_xauusd_m30_logic, get_pair_direction


def _dt_monday():
    return datetime(2026, 7, 6, 4, 45, tzinfo=timezone.utc)  # Monday


class TestApplyXauusdM30Rebuild(unittest.TestCase):
    def test_h3_after_flip_gbpaud_opposite_gbpjpy_same(self):
        """Pattern BUY, XAU M30 same → flip XAU to SELL.
        Then GBPAUD=BUY (opp), GBPJPY=SELL (same)."""
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

    def test_h4_after_flip_gbpaud_opposite_gbpjpy_same(self):
        dt = _dt_monday()
        H = 4
        sig = "SELL"
        pair_dirs = get_pair_direction(H, sig, dt)

        with patch.object(mt5_signal_bot, "get_xauusd_m30_signal", return_value="SELL"):
            # same as sig → flip XAU to BUY
            apply_xauusd_m30_logic(pair_dirs, sig, dt, H)

        self.assertEqual(pair_dirs["XAUUSD"], "BUY")
        self.assertEqual(pair_dirs["GBPAUD"], "SELL")  # opposite XAU
        self.assertEqual(pair_dirs["GBPJPY"], "BUY")   # same XAU

    def test_h4_opposite_m30_keeps_m30_as_final(self):
        dt = _dt_monday()
        H = 4
        sig = "SELL"
        pair_dirs = get_pair_direction(H, sig, dt)

        with patch.object(mt5_signal_bot, "get_xauusd_m30_signal", return_value="BUY"):
            # opposite pattern → final = M30 = BUY
            apply_xauusd_m30_logic(pair_dirs, sig, dt, H)

        self.assertEqual(pair_dirs["XAUUSD"], "BUY")
        self.assertEqual(pair_dirs["GBPAUD"], "SELL")
        self.assertEqual(pair_dirs["GBPJPY"], "BUY")


if __name__ == "__main__":
    unittest.main()
