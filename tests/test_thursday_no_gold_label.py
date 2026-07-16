# -*- coding: utf-8 -*-
"""XAU-only schedule rules: no GBP focus and no no-gold labels."""
import unittest
from datetime import datetime
from unittest.mock import patch

import mt5_signal_bot
from mt5_signal_bot import (
    analyze,
    format_telegram_pair_block,
    get_focus_gbp_pairs,
    get_hour_note,
    get_pair_direction,
    is_xau_no_trade_label_slot,
    xau_no_trade_label_tag,
)


class TestXauOnlyRules(unittest.TestCase):
    def test_no_gold_label_removed_for_all_weekdays(self):
        for weekday in range(5):
            for hour in (2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 15, 17):
                with self.subTest(weekday=weekday, hour=hour):
                    self.assertFalse(is_xau_no_trade_label_slot(hour, weekday=weekday))
                    self.assertEqual(xau_no_trade_label_tag(hour, weekday=weekday), "")

    def test_no_gbp_focus_for_all_weekdays(self):
        for weekday in range(5):
            for hour in (2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 15, 17):
                with self.subTest(weekday=weekday, hour=hour):
                    self.assertEqual(get_focus_gbp_pairs(hour, weekday=weekday), [])

    def test_hour_notes_are_xau_only_except_h2_h17(self):
        for weekday in range(5):
            for hour in (3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 15):
                with self.subTest(weekday=weekday, hour=hour):
                    self.assertEqual(get_hour_note(hour, weekday=weekday), "Chỉ Vàng (XAUUSD)")
            self.assertEqual(get_hour_note(17, weekday=weekday), "XAUUSD theo D-direction H=4")

    def test_h2_notes_vary_by_weekday(self):
        # T3 (weekday=1) / T5 (weekday=3): no reverse
        for wd in (1, 3):
            note = get_hour_note(2, weekday=wd)
            self.assertIn("không đảo", note)
        # T6 (weekday=4): normal, special calendar reverses
        note_fri = get_hour_note(2, weekday=4)
        self.assertIn("bình thường", note_fri)
        # T2 (weekday=0) / T4 (weekday=2): generic
        for wd in (0, 2):
            note = get_hour_note(2, weekday=wd)
            self.assertIn("Chỉ Vàng", note)

    def test_friday_has_no_broad_xau_reversal(self):
        candle = {"open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0}
        friday = datetime(2026, 7, 10, 9, 0)
        with patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=candle):
            result = analyze(friday, 3)
        self.assertEqual(result["signal"], "BUY")

    def test_telegram_block_omits_gbp_and_no_gold(self):
        block = format_telegram_pair_block({"XAUUSD": "BUY"}, 9, weekday=4)
        self.assertNotIn("KHÔNG ĐÁNH", block)
        self.assertIn("XAUUSD: Mua BUY", block)
        self.assertNotIn("GBP", block)

    def test_pair_direction_is_xau_only(self):
        dt = datetime(2026, 7, 9, 12, 0)
        for hour in (2, 3, 5, 9, 12, 15):
            with self.subTest(hour=hour):
                result = get_pair_direction(hour, "BUY", dt)
                self.assertEqual(result, {"XAUUSD": "BUY"})

    def test_h4_keeps_d_direction_marker_only(self):
        result = get_pair_direction(4, "BUY", datetime(2026, 7, 9, 12, 0))
        self.assertEqual(result, {"XAUUSD": "BUY", "D-DIRECTION": "BUY"})


if __name__ == "__main__":
    unittest.main()
