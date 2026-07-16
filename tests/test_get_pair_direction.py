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

    def test_pair_lists_are_xau_only(self):
        self.assertEqual(GBP_PAIRS, [])
        self.assertEqual(ALL_PAIRS, ["XAUUSD"])

    def test_active_slots_have_xauusd_only(self):
        for weekday in range(5):
            for hour in (2, 3, 4, 5, 7, 8, 9, 12, 13, 15):
                for signal in ("BUY", "SELL"):
                    with self.subTest(weekday=weekday, hour=hour, signal=signal):
                        dt = _make_dt(2026, 7, 6, weekday_offset=weekday)
                        result = get_pair_direction(hour, signal, dt)
                        expected = {"XAUUSD": signal}
                        if hour == 4:
                            expected[D_DIRECTION_PAIR] = get_d_direction_from_xau(signal, weekday=weekday)
                        if hour == 5:
                            expected[GBP_DIRECTION_PAIR] = get_d_direction_from_xau(signal, weekday=weekday)
                        self.assertEqual(result, expected)

    def test_non_buy_sell_signal_returns_empty(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=0)
        for signal in ("WAIT", "NONE", "", "HOLD"):
            with self.subTest(signal=signal):
                self.assertEqual(get_pair_direction(6, signal, dt), {})

    def test_h11_h14_are_disabled(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=1)
        for hour in (11, 14):
            with self.subTest(hour=hour):
                self.assertEqual(get_pair_direction(hour, "BUY", dt), {})

    def test_d_direction_helper_follows_xau_on_all_weekdays(self):
        for weekday in range(5):
            with self.subTest(weekday=weekday):
                self.assertEqual(get_d_direction_from_xau("BUY", weekday=weekday), "BUY")
                self.assertEqual(get_d_direction_from_xau("SELL", weekday=weekday), "SELL")


if __name__ == "__main__":
    unittest.main()
