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
    def test_h2_is_disabled(self):
        result = calculate_slot_signal(_dt_tuesday(), 2)
        self.assertEqual(result["signal"], "WAIT")

    def test_h2_thursday_is_disabled(self):
        result = calculate_slot_signal(_dt_thursday(), 2)
        self.assertEqual(result["signal"], "WAIT")

    def test_h2_pair_direction_returns_empty(self):
        dt = _dt_thursday()
        pair_dirs = get_pair_direction(2, "BUY", dt)
        self.assertEqual(pair_dirs, {})

    def test_normal_slots_apply_xau_m30_flip_and_keep_xau_only(self):
        dt = _dt_tuesday()
        for hour in (12, 13, 15):
            with self.subTest(hour=hour):
                pair_dirs = get_pair_direction(hour, "BUY", dt)
                with patch.object(mt5_signal_bot, "get_xauusd_m30_signal", return_value="BUY"):
                    apply_xauusd_m30_logic(pair_dirs, "BUY", dt, hour)
                self.assertEqual(pair_dirs["XAUUSD"], "SELL")
                self.assertEqual(set(pair_dirs).difference({"XAUUSD"}), set())


if __name__ == "__main__":
    unittest.main()
