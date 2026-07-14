# -*- coding: utf-8 -*-
"""Unit tests for XAU-only pair direction rules."""
import unittest
from datetime import datetime, timezone

from mt5_signal_bot import (
    ALL_PAIRS,
    D_DIRECTION_PAIR,
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
            for hour in (2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 15):
                for signal in ("BUY", "SELL"):
                    with self.subTest(weekday=weekday, hour=hour, signal=signal):
                        dt = _make_dt(2026, 7, 6, weekday_offset=weekday)
                        result = get_pair_direction(hour, signal, dt)
                        expected = {"XAUUSD": signal}
                        if hour == 4:
                            expected[D_DIRECTION_PAIR] = get_d_direction_from_xau(signal, weekday=weekday)
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

    def test_h17_uses_stored_d_direction_for_xauusd(self):
        dt = _make_dt(2026, 7, 6, weekday_offset=0)
        self.assertEqual(get_pair_direction(17, "BUY", dt), {})
        self.assertEqual(
            get_pair_direction(17, "BUY", dt, d_direction="SELL"),
            {"XAUUSD": "SELL"},
        )

    def test_d_direction_helper_opposite_on_monday_and_friday(self):
        self.assertEqual(get_d_direction_from_xau("BUY", weekday=0), "SELL")
        self.assertEqual(get_d_direction_from_xau("BUY", weekday=4), "SELL")
        self.assertEqual(get_d_direction_from_xau("BUY", weekday=1), "BUY")


if __name__ == "__main__":
    unittest.main()
