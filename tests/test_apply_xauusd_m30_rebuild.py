# -*- coding: utf-8 -*-
"""XAU M30 flip: H=2-4 rebuild GBP from final XAU; H=5+ XAU only."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import mt5_signal_bot
from mt5_signal_bot import (
    analyze,
    apply_xauusd_m30_logic,
    get_pair_direction,
    is_h2_special_calendar_weekday,
)


def _dt_tuesday():
    return datetime(2026, 7, 7, 4, 45, tzinfo=timezone.utc)  # Tuesday


def _dt_thursday():
    return datetime(2026, 7, 9, 2, 45, tzinfo=timezone.utc)


class TestApplyXauusdM30Rebuild(unittest.TestCase):
    def test_regular_thursday_h2_analysis_reverses_and_skips_h1_gold(self):
        candle = {"open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0}
        with patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=candle), patch.object(
            mt5_signal_bot, "get_h1_candle_for_slot"
        ) as h1_candle:
            result = analyze(_dt_thursday(), 2)
        self.assertEqual(result["signal"], "SELL")
        h1_candle.assert_not_called()

    def test_h2_tuesday_also_reverses_signal(self):
        candle = {"open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0}
        tuesday = _dt_thursday().replace(day=7)
        with patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=candle):
            result = analyze(tuesday, 2)
        self.assertEqual(result["signal"], "SELL")

    def test_h2_special_thursday_keeps_xau_normal(self):
        candle = {"open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0}
        cases = (
            datetime(2025, 5, 1, 2, 45, tzinfo=timezone.utc),  # Wed Apr 30
            datetime(2025, 1, 2, 2, 45, tzinfo=timezone.utc),  # Fri Jan 3 same week
        )
        for dt in cases:
            with self.subTest(dt=dt):
                self.assertTrue(is_h2_special_calendar_weekday(dt))
                with patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=candle):
                    result = analyze(dt, 2)
                self.assertEqual(result["signal"], "BUY")

    def test_h2_special_friday_reverses(self):
        candle = {"open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0}
        friday = datetime(2025, 1, 3, 2, 45, tzinfo=timezone.utc)
        self.assertTrue(is_h2_special_calendar_weekday(friday))
        with patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=candle):
            result = analyze(friday, 2)
        self.assertEqual(result["signal"], "SELL")

    def test_regular_thursday_h2_reverses_by_default(self):
        candle = {"open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0}
        thursday = datetime(2026, 7, 9, 2, 45, tzinfo=timezone.utc)
        self.assertFalse(is_h2_special_calendar_weekday(thursday))
        with patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=candle):
            result = analyze(thursday, 2)
        self.assertEqual(result["signal"], "SELL")

    def test_regular_friday_h2_does_not_reverse(self):
        candle = {"open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0}
        friday = datetime(2026, 7, 10, 2, 45, tzinfo=timezone.utc)
        self.assertFalse(is_h2_special_calendar_weekday(friday))
        with patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=candle):
            result = analyze(friday, 2)
        self.assertEqual(result["signal"], "BUY")

    def test_h2_rebuilds_both_gbp_pairs_after_m30_flip(self):
        dt = _dt_thursday()
        pair_dirs = get_pair_direction(2, "BUY", dt)
        with patch.object(mt5_signal_bot, "get_xauusd_m30_signal", return_value="BUY"):
            apply_xauusd_m30_logic(pair_dirs, "BUY", dt, 2)
        self.assertEqual(pair_dirs["XAUUSD"], "SELL")
        self.assertEqual(pair_dirs["GBPAUD"], "BUY")
        self.assertEqual(pair_dirs["GBPJPY"], "BUY")

    def test_h3_after_flip_gbp_pairs_are_both_opposite(self):
        """H=3-4: both GBP pairs are opposite the final XAU direction."""
        dt = _dt_tuesday()
        H = 3
        sig = "BUY"
        pair_dirs = get_pair_direction(H, sig, dt)
        self.assertEqual(pair_dirs["XAUUSD"], "BUY")
        self.assertEqual(pair_dirs["GBPAUD"], "SELL")
        self.assertEqual(pair_dirs["GBPJPY"], "SELL")

        with patch.object(mt5_signal_bot, "get_xauusd_m30_signal", return_value="BUY"):
            apply_xauusd_m30_logic(pair_dirs, sig, dt, H)

        self.assertEqual(pair_dirs["XAUUSD"], "SELL")
        self.assertEqual(pair_dirs["GBPAUD"], "BUY")
        self.assertEqual(pair_dirs["GBPJPY"], "BUY")
        self.assertEqual(pair_dirs["GBPUSD"], "--")
        self.assertEqual(pair_dirs["GBPCAD"], "--")

    def test_h5_xau_only_after_flip(self):
        """H=5-8: Focus only — no GBP in pair_dirs even after M30 flip."""
        dt = _dt_tuesday()
        for H in (5, 6, 7, 8):
            with self.subTest(H=H):
                sig = "SELL"
                pair_dirs = get_pair_direction(H, sig, dt)
                self.assertEqual(pair_dirs, {"XAUUSD": "SELL"})
                with patch.object(mt5_signal_bot, "get_xauusd_m30_signal", return_value="SELL"):
                    apply_xauusd_m30_logic(pair_dirs, sig, dt, H)
                self.assertEqual(pair_dirs["XAUUSD"], "BUY")
                for p in ("GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"):
                    self.assertNotIn(p, pair_dirs)

    def test_h9_plus_xau_only_after_flip(self):
        dt = _dt_tuesday()
        for H in (9, 12, 15):
            with self.subTest(H=H):
                sig = "BUY"
                pair_dirs = get_pair_direction(H, sig, dt)
                self.assertEqual(pair_dirs, {"XAUUSD": "BUY"})
                with patch.object(mt5_signal_bot, "get_xauusd_m30_signal", return_value="BUY"):
                    apply_xauusd_m30_logic(pair_dirs, sig, dt, H)
                self.assertEqual(pair_dirs["XAUUSD"], "SELL")
                for p in ("GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"):
                    self.assertNotIn(p, pair_dirs)


if __name__ == "__main__":
    unittest.main()
