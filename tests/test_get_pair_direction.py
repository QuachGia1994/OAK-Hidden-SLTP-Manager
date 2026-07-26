# -*- coding: utf-8 -*-
"""Unit tests for XAU-only pair direction rules."""
import unittest
from datetime import datetime, timezone

from mt5_signal_bot import (
    ALL_PAIRS,
    D_DIRECTION_PAIR,
    GBP_DIRECTION_PAIR,
    GBP_PAIRS,
    get_d_direction_from_xau,
    get_pair_direction,
)


def _make_dt(year, month, day, weekday_offset=0):
    """Create a timezone-aware datetime for a given weekday."""
    dt = datetime(year, month, day, tzinfo=timezone.utc)
    while dt.weekday() != weekday_offset:
        dt = dt.replace(day=dt.day + 1)
    return dt


class TestGetPairDirectionHSlots(unittest.TestCase):
    """Test XAU-only H-slot direction rules."""

    def test_pair_lists(self):
        self.assertEqual(GBP_PAIRS, ["GBPAUD", "GBPCAD", "GBPJPY", "GBPUSD"])
        self.assertEqual(ALL_PAIRS, ["XAUUSD", "GBPAUD", "GBPCAD", "GBPJPY", "GBPUSD"])

    def test_xauusd_slots_have_xauusd_only(self):
        for weekday in range(5):
            for hour in (3, 4, 5, 6, 12, 14, 16):
                for signal in ("BUY", "SELL"):
                    with self.subTest(weekday=weekday, hour=hour, signal=signal):
                        dt = _make_dt(2026, 7, 6, weekday_offset=weekday)
                        result = get_pair_direction(hour, signal, dt)
                        self.assertIn("XAUUSD", result)
                        self.assertEqual(result["XAUUSD"], signal)

    def test_h9_returns_gbp_group_and_xau(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=1)
        # H=9 MIXED: pair_dirs come from calculate_slot_signal
        full_result = {"pair_dirs": {"XAUUSD": "BUY", "GBPUSD": "BUY", "GBPAUD": "BUY"}}
        result = get_pair_direction(9, "BUY", dt, full_result=full_result)
        self.assertIn("XAUUSD", result)
        self.assertEqual(result.get("GBPAUD"), "BUY")
        self.assertEqual(result.get("GBPUSD"), "BUY")

    def test_h14_returns_xauusd_and_gbp_group(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=1)
        # H=14: pair_dirs come from calculate_slot_signal
        full_result = {"pair_dirs": {"XAUUSD": "SELL", "GBPUSD": "SELL", "GBPAUD": "SELL"}}
        result = get_pair_direction(14, "SELL", dt, full_result=full_result)
        self.assertIn("XAUUSD", result)
        self.assertEqual(result["XAUUSD"], "SELL")
        self.assertEqual(result.get("GBPAUD"), "SELL")
        self.assertEqual(result.get("GBPUSD"), "SELL")

    def test_wednesday_keeps_gbp_for_h9_and_h14(self):
        wednesday = _make_dt(2026, 7, 6, weekday_offset=2)
        for hour in (9, 14):
            with self.subTest(hour=hour):
                full_result = {
                    "pair_dirs": {
                        "XAUUSD": "BUY",
                        "GBPUSD": "BUY",
                        "GBPAUD": "SELL",
                    }
                }
                result = get_pair_direction(hour, "BUY", wednesday, full_result=full_result)
                self.assertEqual(result["GBPUSD"], "BUY")
                self.assertEqual(result["GBPAUD"], "SELL")

    def test_non_buy_sell_signal_returns_empty(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=0)
        for signal in ("NONE", "", "HOLD"):
            with self.subTest(signal=signal):
                self.assertEqual(get_pair_direction(6, signal, dt), {})

    def test_wait_signal_returns_xauusd_wait(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=0)
        result = get_pair_direction(6, "WAIT", dt)
        self.assertEqual(result, {"XAUUSD": "WAIT"})



    def test_d_direction_helper_follows_xau_on_all_weekdays(self):
        for weekday in range(5):
            with self.subTest(weekday=weekday):
                self.assertEqual(get_d_direction_from_xau("BUY", weekday=weekday), "BUY")
                self.assertEqual(get_d_direction_from_xau("SELL", weekday=weekday), "SELL")


if __name__ == "__main__":
    unittest.main()
