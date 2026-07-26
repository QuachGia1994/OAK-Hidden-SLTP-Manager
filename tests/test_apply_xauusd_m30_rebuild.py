# -*- coding: utf-8 -*-
"""Regression coverage for XAU M30 post-processing and the H-slot matrix."""
from datetime import datetime, timezone
from unittest.mock import patch
import unittest

import mt5_signal_bot
from mt5_signal_bot import (
    apply_xauusd_m30_logic,
    calculate_slot_signal,
    get_pair_direction,
)


def _dt_tuesday():
    return datetime(2026, 7, 7, 4, 45, tzinfo=timezone.utc)


def _dt_thursday():
    return datetime(2026, 7, 9, 2, 45, tzinfo=timezone.utc)


class TestApplyXauusdM30Rebuild(unittest.TestCase):
    def test_h3_is_the_active_logical_early_slot(self):
        self.assertIn(3, mt5_signal_bot.ACTIVE_HOURS)
        self.assertNotIn(2, mt5_signal_bot.ACTIVE_HOURS)

    def test_h3_pair_direction_includes_opposite_gbpaud(self):
        dt = _dt_thursday()
        pair_dirs = get_pair_direction(3, "BUY", dt)
        self.assertEqual(pair_dirs["XAUUSD"], "BUY")
        self.assertEqual(pair_dirs["GBPAUD"], "SELL")

    def test_normal_slots_apply_xau_m30_flip_and_keep_direction_marker(self):
        dt = _dt_tuesday()
        for hour in (4, 5):
            with self.subTest(hour=hour):
                pair_dirs = get_pair_direction(hour, "BUY", dt)
                with patch.object(mt5_signal_bot, "get_xauusd_m30_signal", return_value="BUY"):
                    apply_xauusd_m30_logic(pair_dirs, "BUY", dt, hour)
                self.assertEqual(pair_dirs["XAUUSD"], "SELL")
                marker = "Stock-DIRECTION" if hour == 4 else "GBP-DIRECTION"
                self.assertEqual(pair_dirs[marker], "SELL")


if __name__ == "__main__":
    unittest.main()
