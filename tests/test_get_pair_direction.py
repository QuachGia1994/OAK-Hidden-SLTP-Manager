# -*- coding: utf-8 -*-
"""Unit tests for pair direction rules with GBP pairs."""
import unittest
from datetime import datetime, timezone

from mt5_signal_bot import (
    ALL_PAIRS,
    GBP_PAIRS,
    get_pair_direction,
)


def _make_dt(year, month, day, weekday_offset=0):
    """Create a timezone-aware datetime for a given weekday."""
    dt = datetime(year, month, day, tzinfo=timezone.utc)
    while dt.weekday() != weekday_offset:
        dt = dt.replace(day=dt.day + 1)
    return dt


class TestGetPairDirectionHSlots(unittest.TestCase):
    """Test H-slot direction rules with XAUUSD + GBP pairs."""

    def test_pair_lists(self):
        self.assertEqual(GBP_PAIRS, ["GBPAUD", "GBPCAD", "GBPJPY", "GBPUSD"])
        self.assertEqual(ALL_PAIRS, ["XAUUSD", "GBPAUD", "GBPCAD", "GBPJPY", "GBPUSD"])

    def test_xauusd_slots_have_xauusd_only_without_full_result(self):
        """Without full_result, only XAUUSD is returned."""
        for weekday in range(5):
            for hour in (3, 4, 6, 9, 12, 14, 16):
                for signal in ("BUY", "SELL"):
                    with self.subTest(weekday=weekday, hour=hour, signal=signal):
                        dt = _make_dt(2026, 7, 6, weekday_offset=weekday)
                        result = get_pair_direction(hour, signal, dt)
                        self.assertIn("XAUUSD", result)
                        self.assertEqual(result["XAUUSD"], signal)
                        self.assertEqual(result, {"XAUUSD": signal})

    def test_h9_includes_gbp_pairs_from_full_result(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=1)
        full_result = {"pair_dirs": {"XAUUSD": "BUY", "GBPUSD": "BUY", "GBPAUD": "BUY"}}
        result = get_pair_direction(9, "BUY", dt, full_result=full_result)
        self.assertEqual(result["XAUUSD"], "BUY")
        self.assertIn("GBPUSD", result)
        self.assertIn("GBPAUD", result)

    def test_h14_includes_gbp_pairs_from_full_result(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=1)
        full_result = {"pair_dirs": {"XAUUSD": "SELL", "GBPUSD": "SELL", "GBPAUD": "SELL"}}
        result = get_pair_direction(14, "SELL", dt, full_result=full_result)
        self.assertEqual(result["XAUUSD"], "SELL")
        self.assertIn("GBPUSD", result)
        self.assertIn("GBPAUD", result)

    def test_wednesday_includes_gbp_pairs(self):
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
                self.assertEqual(result["XAUUSD"], "BUY")
                self.assertIn("GBPUSD", result)
                self.assertIn("GBPAUD", result)

    def test_non_buy_sell_signal_returns_empty(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=0)
        for signal in ("NONE", "", "HOLD"):
            with self.subTest(signal=signal):
                self.assertEqual(get_pair_direction(6, signal, dt), {})

    def test_wait_signal_returns_xauusd_wait(self):
        dt = _make_dt(2026, 7, 7, weekday_offset=0)
        result = get_pair_direction(6, "WAIT", dt)
        self.assertEqual(result, {"XAUUSD": "WAIT"})


if __name__ == "__main__":
    unittest.main()
