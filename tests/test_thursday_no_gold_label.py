# -*- coding: utf-8 -*-
"""XAU-only schedule rules: no GBP focus and no no-gold labels."""
from datetime import datetime
from unittest.mock import patch
import unittest

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
            for hour in (4, 5, 12, 13, 15):
                with self.subTest(weekday=weekday, hour=hour):
                    self.assertFalse(is_xau_no_trade_label_slot(hour, weekday=weekday))
                    self.assertEqual(xau_no_trade_label_tag(hour, weekday=weekday), "")

    def test_no_gbp_focus_for_all_weekdays(self):
        for weekday in range(5):
            for hour in (4, 5, 12, 13, 15):
                with self.subTest(weekday=weekday, hour=hour):
                    self.assertEqual(get_focus_gbp_pairs(hour, weekday=weekday), [])

    def test_hour_notes_explain_h3_and_keep_other_slots_xau_only(self):
        for weekday in range(5):
            for hour in (4, 5, 12, 13, 15):
                with self.subTest(weekday=weekday, hour=hour):
                    self.assertEqual(get_hour_note(hour, weekday=weekday), "Chỉ Vàng (XAUUSD)")

    def test_raw_analysis_has_no_weekday_reversal(self):
        candle = {"open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0}
        with patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=candle):
            result = analyze(datetime(2026, 7, 10, 9, 0), 3)
        self.assertEqual(result["signal"], "BUY")

    def test_telegram_block_omits_gbp_and_no_gold(self):
        block = format_telegram_pair_block({"XAUUSD": "BUY"}, 9, weekday=4)
        self.assertIn("XAUUSD: Mua BUY", block)
        self.assertNotIn("GBP", block)

    def test_pair_direction_is_xau_only(self):
        dt = datetime(2026, 7, 9, 12, 0)
        for hour in (12, 15):
            with self.subTest(hour=hour):
                self.assertEqual(get_pair_direction(hour, "BUY", dt), {"XAUUSD": "BUY"})


if __name__ == "__main__":
    unittest.main()
