# -*- coding: utf-8 -*-
"""Unit tests for get_pair_direction() H-slot rules."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import mt5_signal_bot
from mt5_signal_bot import get_pair_direction, GBP_PAIRS


def _make_dt(year, month, day, weekday_offset=0):
    """Create a timezone-aware datetime for a given weekday."""
    dt = datetime(year, month, day, tzinfo=timezone.utc)
    while dt.weekday() != weekday_offset:
        dt = dt.replace(day=dt.day + 1)
    return dt


# Patch helpers to isolate from global d_direction state
_PATCHERS = [
    patch.object(mt5_signal_bot, "get_effective_d_direction", return_value=None),
    patch.object(mt5_signal_bot, "d_direction_date", None),
]


def setUpModule():
    for p in _PATCHERS:
        p.start()


def tearDownModule():
    for p in _PATCHERS:
        p.stop()


class TestGetPairDirectionHSlots(unittest.TestCase):
    """Test H-slot-based pair direction rules (live code after dead code removal)."""

    def test_h2_3_gbpaud_gbpjpy_opposite(self):
        """H=2,3: GBPAUD + GBPJPY opposite to gold; GBPUSD + GBPCAD = '--'"""
        for H in (2, 3):
            for signal in ("BUY", "SELL"):
                with self.subTest(H=H, signal=signal):
                    dt = _make_dt(2026, 7, 7, weekday_offset=0)
                    result = get_pair_direction(H, signal, dt)
                    opposite = "SELL" if signal == "BUY" else "BUY"
                    self.assertEqual(result["XAUUSD"], signal)
                    self.assertEqual(result["GBPAUD"], opposite)
                    self.assertEqual(result["GBPJPY"], opposite)
                    self.assertEqual(result["GBPUSD"], "--")
                    self.assertEqual(result["GBPCAD"], "--")

    def test_h4_6_gbpaud_opposite(self):
        """H=4,6: GBPAUD opposite; rest = '--'"""
        for H in (4, 6):
            for signal in ("BUY", "SELL"):
                with self.subTest(H=H, signal=signal):
                    dt = _make_dt(2026, 7, 7, weekday_offset=0)
                    result = get_pair_direction(H, signal, dt)
                    opposite = "SELL" if signal == "BUY" else "BUY"
                    self.assertEqual(result["XAUUSD"], signal)
                    self.assertEqual(result["GBPAUD"], opposite)
                    self.assertEqual(result["GBPUSD"], "--")
                    self.assertEqual(result["GBPCAD"], "--")
                    self.assertEqual(result["GBPJPY"], "--")

    def test_h9_11_all_gbp_opposite(self):
        """H=9,11: all GBP pairs opposite to gold"""
        for H in (9, 11):
            for signal in ("BUY", "SELL"):
                with self.subTest(H=H, signal=signal):
                    dt = _make_dt(2026, 7, 7, weekday_offset=0)
                    result = get_pair_direction(H, signal, dt)
                    opposite = "SELL" if signal == "BUY" else "BUY"
                    self.assertEqual(result["XAUUSD"], signal)
                    for p in GBP_PAIRS:
                        self.assertEqual(result[p], opposite, f"{p} should be {opposite}")

    def test_h12_15_all_gbp_same(self):
        """H=12,15: all GBP pairs same direction as gold"""
        for H in (12, 15):
            for signal in ("BUY", "SELL"):
                with self.subTest(H=H, signal=signal):
                    dt = _make_dt(2026, 7, 7, weekday_offset=0)
                    result = get_pair_direction(H, signal, dt)
                    self.assertEqual(result["XAUUSD"], signal)
                    for p in GBP_PAIRS:
                        self.assertEqual(result[p], signal, f"{p} should be {signal}")

    def test_other_hours_xauusd_only(self):
        """H=14,16,0,1,5,7,8,10,13: only XAUUSD in result"""
        for H in (0, 1, 5, 7, 8, 10, 13, 14, 16):
            with self.subTest(H=H):
                dt = _make_dt(2026, 7, 7, weekday_offset=0)
                result = get_pair_direction(H, "BUY", dt)
                self.assertEqual(result, {"XAUUSD": "BUY"})

    def test_non_buy_sell_signal_returns_empty(self):
        """Non-BUY/SELL signal returns empty dict"""
        dt = _make_dt(2026, 7, 7, weekday_offset=0)
        for signal in ("WAIT", "NONE", "", "HOLD"):
            with self.subTest(signal=signal):
                result = get_pair_direction(6, signal, dt)
                self.assertEqual(result, {})

    def test_buy_and_sell_opposite_directions(self):
        """BUY signal gives SELL for opposite, and vice versa"""
        dt = _make_dt(2026, 7, 7, weekday_offset=0)
        buy_result = get_pair_direction(9, "BUY", dt)
        sell_result = get_pair_direction(9, "SELL", dt)
        self.assertEqual(buy_result["XAUUSD"], "BUY")
        self.assertEqual(sell_result["XAUUSD"], "SELL")
        for p in GBP_PAIRS:
            self.assertEqual(buy_result[p], "SELL")
            self.assertEqual(sell_result[p], "BUY")

    def test_all_active_slots_have_xauusd(self):
        """Every active slot (H=2,3,4,6,9,11,12,15) must include XAUUSD"""
        dt = _make_dt(2026, 7, 7, weekday_offset=0)
        for H in (2, 3, 4, 6, 9, 11, 12, 15):
            with self.subTest(H=H):
                result = get_pair_direction(H, "BUY", dt)
                self.assertIn("XAUUSD", result)

    def test_works_on_all_weekdays(self):
        """H-slot rules are weekday-agnostic: same result for Mon-Fri"""
        for weekday in range(5):
            with self.subTest(weekday=weekday):
                dt = _make_dt(2026, 7, 7, weekday_offset=weekday)
                result = get_pair_direction(6, "BUY", dt)
                self.assertEqual(result["XAUUSD"], "BUY")
                self.assertEqual(result["GBPAUD"], "SELL")
                self.assertEqual(result["GBPUSD"], "--")
                self.assertEqual(result["GBPCAD"], "--")
                self.assertEqual(result["GBPJPY"], "--")


if __name__ == "__main__":
    unittest.main()
