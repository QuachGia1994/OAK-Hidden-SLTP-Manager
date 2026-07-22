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
            for hour in (2, 3, 4, 5, 7, 8, 12, 13, 15):
                for signal in ("BUY", "SELL"):
                    with self.subTest(weekday=weekday, hour=hour, signal=signal):
                        dt = _make_dt(2026, 7, 6, weekday_offset=weekday)
                        result = get_pair_direction(hour, signal, dt)
                        self.assertIn("XAUUSD", result)
                        self.assertEqual(result["XAUUSD"], signal)

    def test_h9_returns_gbp_group_no_xau(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=1)
        result = get_pair_direction(9, "BUY", dt)
        self.assertNotIn("XAUUSD", result)
        self.assertEqual(result.get("GBPAUD"), "BUY")
        self.assertEqual(result.get("GBPCAD"), "BUY")
        self.assertEqual(result.get("GBPJPY"), "BUY")
        self.assertEqual(result.get("GBPUSD"), "BUY")

    def test_h14_returns_gbp_group_no_xau(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=1)
        result = get_pair_direction(14, "SELL", dt)
        self.assertNotIn("XAUUSD", result)
        self.assertEqual(result.get("GBPAUD"), "SELL")
        self.assertEqual(result.get("GBPCAD"), "SELL")
        self.assertEqual(result.get("GBPJPY"), "SELL")
        self.assertEqual(result.get("GBPUSD"), "SELL")

    def test_non_buy_sell_signal_returns_empty(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=0)
        for signal in ("WAIT", "NONE", "", "HOLD"):
            with self.subTest(signal=signal):
                self.assertEqual(get_pair_direction(6, signal, dt), {})

    def test_disabled_hours_return_no_pair_direction(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=1)
        for hour in (6, 10, 17):
            with self.subTest(hour=hour):
                self.assertEqual(get_pair_direction(hour, "BUY", dt), {})

    def test_d_direction_helper_follows_xau_on_all_weekdays(self):
        for weekday in range(5):
            with self.subTest(weekday=weekday):
                self.assertEqual(get_d_direction_from_xau("BUY", weekday=weekday), "BUY")
                self.assertEqual(get_d_direction_from_xau("SELL", weekday=weekday), "SELL")


if __name__ == "__main__":
    unittest.main()
