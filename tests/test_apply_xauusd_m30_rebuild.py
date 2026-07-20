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
    is_h2_special_calendar_weekday,
    should_reverse_h2_xau,
)


def _dt_tuesday():
    return datetime(2026, 7, 7, 4, 45, tzinfo=timezone.utc)


def _dt_thursday():
    return datetime(2026, 7, 9, 2, 45, tzinfo=timezone.utc)


class TestApplyXauusdM30Rebuild(unittest.TestCase):
    def test_regular_thursday_h2_reuses_monday_final_h2(self):
        candle = {"open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0}
        with patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=candle), patch.object(
            mt5_signal_bot, "_lookup_h2_t2_signal", return_value="SELL"
        ):
            result = calculate_slot_signal(_dt_thursday(), 2)
        self.assertEqual(result["signal"], "SELL")
        self.assertIn("lịch sử Thứ 2", result["report"])

    def test_regular_h2_applies_xau_m30_post_process(self):
        candle = {"open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0}
        with patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=candle):
            result = calculate_slot_signal(_dt_tuesday(), 2)
        # M5/M30 produces BUY, matching XAU M30 produces final SELL.
        self.assertEqual(result["pattern_signal"], "BUY")
        self.assertEqual(result["signal"], "SELL")

    def test_thursday_without_monday_h2_falls_back_to_pattern(self):
        candle = {"open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0}
        with patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=candle), patch.object(
            mt5_signal_bot, "_lookup_h2_t2_signal", return_value=None
        ):
            result = calculate_slot_signal(_dt_thursday(), 2)
        self.assertEqual(result["signal"], "SELL")
        self.assertIn("PATTERN", result["report"])

    def test_special_thursday_reverses_monday_h2_final(self):
        for dt in (
            datetime(2025, 5, 1, 2, 45, tzinfo=timezone.utc),
            datetime(2025, 1, 2, 2, 45, tzinfo=timezone.utc),
        ):
            with self.subTest(dt=dt), patch.object(
                mt5_signal_bot, "_lookup_h2_t2_signal", return_value="BUY"
            ):
                self.assertTrue(is_h2_special_calendar_weekday(dt))
                self.assertEqual(calculate_slot_signal(dt, 2)["signal"], "SELL")

    def test_special_calendar_friday_keeps_normal_h2_logic(self):
        candle = {"open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0}
        friday = datetime(2025, 1, 3, 2, 45, tzinfo=timezone.utc)
        self.assertFalse(is_h2_special_calendar_weekday(friday))
        self.assertFalse(should_reverse_h2_xau(friday))
        with patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=candle):
            result = calculate_slot_signal(friday, 2)
        self.assertEqual(result["signal"], "SELL")

    def test_regular_friday_h2_uses_normal_xau_m30_post_process(self):
        candle = {"open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0}
        friday = datetime(2026, 7, 10, 2, 45, tzinfo=timezone.utc)
        self.assertFalse(is_h2_special_calendar_weekday(friday))
        with patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=candle):
            result = calculate_slot_signal(friday, 2)
        self.assertEqual(result["signal"], "SELL")

    def test_h2_updates_xau_only_after_m30_flip(self):
        dt = _dt_thursday()
        pair_dirs = get_pair_direction(2, "BUY", dt)
        with patch.object(mt5_signal_bot, "get_xauusd_m30_signal", return_value="BUY"):
            apply_xauusd_m30_logic(pair_dirs, "BUY", dt, 2)
        self.assertEqual(pair_dirs, {"XAUUSD": "SELL"})

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
