# -*- coding: utf-8 -*-
"""Unit tests for get_pair_direction() H-slot rules."""
import unittest
from datetime import datetime, timezone

from mt5_signal_bot import get_pair_direction, GBP_PAIRS


def _make_dt(year, month, day, weekday_offset=0):
    """Create a timezone-aware datetime for a given weekday."""
    dt = datetime(year, month, day, tzinfo=timezone.utc)
    while dt.weekday() != weekday_offset:
        dt = dt.replace(day=dt.day + 1)
    return dt


class TestGetPairDirectionHSlots(unittest.TestCase):
    """Test H-slot-based pair direction rules."""

    def test_h3_to_h4_gbpjpy_same_gbpaud_opposite(self):
        """H=3-4: GBPJPY same XAUUSD; GBPAUD opposite; GBPUSD/GBPCAD = '--'"""
        for H in (3, 4):
            for signal in ("BUY", "SELL"):
                with self.subTest(H=H, signal=signal):
                    dt = _make_dt(2026, 7, 7, weekday_offset=0)
                    result = get_pair_direction(H, signal, dt)
                    opposite = "SELL" if signal == "BUY" else "BUY"
                    self.assertEqual(result["XAUUSD"], signal)
                    self.assertEqual(result["GBPJPY"], signal)
                    self.assertEqual(result["GBPAUD"], opposite)
                    self.assertEqual(result["GBPUSD"], "--")
                    self.assertEqual(result["GBPCAD"], "--")

    def test_h5_plus_xauusd_only(self):
        """H=5+ (incl 5-8 Focus and 9+): only XAUUSD — no GBP pair_dirs map."""
        for H in (5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16):
            for signal in ("BUY", "SELL"):
                with self.subTest(H=H, signal=signal):
                    dt = _make_dt(2026, 7, 7, weekday_offset=0)
                    result = get_pair_direction(H, signal, dt)
                    self.assertEqual(result, {"XAUUSD": signal})
                    for p in GBP_PAIRS:
                        self.assertNotIn(p, result)

    def test_h2_is_not_a_gbp_direction_slot(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=0)
        self.assertEqual(get_pair_direction(2, "BUY", dt), {"XAUUSD": "BUY"})

    def test_non_buy_sell_signal_returns_empty(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=0)
        for signal in ("WAIT", "NONE", "", "HOLD"):
            with self.subTest(signal=signal):
                result = get_pair_direction(6, signal, dt)
                self.assertEqual(result, {})

    def test_h3_opposite_on_buy_sell(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=0)
        buy_result = get_pair_direction(3, "BUY", dt)
        sell_result = get_pair_direction(3, "SELL", dt)
        self.assertEqual(buy_result["XAUUSD"], "BUY")
        self.assertEqual(sell_result["XAUUSD"], "SELL")
        self.assertEqual(buy_result["GBPAUD"], "SELL")
        self.assertEqual(sell_result["GBPAUD"], "BUY")

    def test_all_active_slots_have_xauusd(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=0)
        for H in (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15):
            with self.subTest(H=H):
                result = get_pair_direction(H, "BUY", dt)
                self.assertIn("XAUUSD", result)

    def test_works_on_all_weekdays(self):
        for weekday in (0, 1, 2):
            with self.subTest(weekday=weekday):
                dt = _make_dt(2026, 7, 7, weekday_offset=weekday)
                result = get_pair_direction(3, "BUY", dt)
                self.assertEqual(result["XAUUSD"], "BUY")
                self.assertEqual(result["GBPAUD"], "SELL")
                self.assertEqual(result["GBPJPY"], "BUY")

    def test_thursday_and_friday_h3_are_xau_only(self):
        for weekday in (3, 4):
            with self.subTest(weekday=weekday):
                dt = _make_dt(2026, 7, 7, weekday_offset=weekday)
                self.assertEqual(get_pair_direction(3, "BUY", dt), {"XAUUSD": "BUY"})


if __name__ == "__main__":
    unittest.main()
