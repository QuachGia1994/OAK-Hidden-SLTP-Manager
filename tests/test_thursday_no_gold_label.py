# -*- coding: utf-8 -*-
"""Schedule rules for Thursday no-gold labels and Friday GBP Focus."""
import unittest
from datetime import datetime

from mt5_signal_bot import (
    format_telegram_pair_block,
    get_focus_gbp_pairs,
    get_hour_note,
    get_pair_direction,
    is_xau_no_trade_label_slot,
    xau_no_trade_label_tag,
)


class TestThursdayAndFridayRules(unittest.TestCase):
    def test_thursday_only_h3_h4_are_no_gold(self):
        thursday = datetime(2026, 7, 9, 13, 0)
        for hour in (3, 4):
            self.assertTrue(is_xau_no_trade_label_slot(hour, thursday))
            self.assertEqual(xau_no_trade_label_tag(hour, thursday), "H=3-4")
        for hour in (12, 13, 14, 15):
            self.assertFalse(is_xau_no_trade_label_slot(hour, thursday))
            self.assertEqual(xau_no_trade_label_tag(hour, thursday), "")

    def test_friday_has_no_gbp_focus(self):
        for hour in range(3, 16):
            self.assertEqual(get_focus_gbp_pairs(hour, weekday=4), [])
            self.assertEqual(get_hour_note(hour, weekday=4), "Chỉ Vàng (XAUUSD)")

    def test_friday_telegram_block_omits_gbp(self):
        block = format_telegram_pair_block({"XAUUSD": "BUY"}, 9, weekday=4)
        self.assertIn("KHÔNG ĐÁNH", block)
        self.assertNotIn("GBP", block)

    def test_thursday_focus_schedule(self):
        thursday = datetime(2026, 7, 9, 12, 0)
        for hour in (3, 4):
            self.assertEqual(get_focus_gbp_pairs(hour, weekday=3), [])
            self.assertEqual(get_hour_note(hour, weekday=3), "Chỉ Vàng (XAUUSD)")
            self.assertEqual(get_pair_direction(hour, "BUY", thursday), {"XAUUSD": "BUY"})
        for hour in (5, 6, 7, 8):
            self.assertEqual(get_focus_gbp_pairs(hour, weekday=3), ["GBPAUD"])
            self.assertEqual(get_hour_note(hour, weekday=3), "Chỉ Focus GBPAUD")
        expected = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"]
        for hour in (9, 11, 12, 15):
            self.assertEqual(get_focus_gbp_pairs(hour, weekday=3), expected)

    def test_tuesday_and_wednesday_focus_only_gbpaud_in_nhip_2(self):
        for weekday in (1, 2):
            for hour in (5, 6, 7, 8):
                with self.subTest(weekday=weekday, hour=hour):
                    self.assertEqual(get_focus_gbp_pairs(hour, weekday=weekday), ["GBPAUD"])

    def test_monday_to_thursday_focus_is_unchanged(self):
        expected = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"]
        for weekday in range(1, 4):
            self.assertEqual(get_focus_gbp_pairs(12, weekday=weekday), expected)

    def test_monday_rule(self):
        for hour in (3, 4):
            self.assertTrue(is_xau_no_trade_label_slot(hour, weekday=0))
            self.assertEqual(xau_no_trade_label_tag(hour, weekday=0), "T2 H=3-4")
        for hour in range(5, 12):
            self.assertTrue(is_xau_no_trade_label_slot(hour, weekday=0))
        self.assertEqual(get_focus_gbp_pairs(9, weekday=0), ["GBPUSD", "GBPCAD"])
        for hour in (3, 4, 5, 8, 10, 11, 12, 15):
            self.assertEqual(get_focus_gbp_pairs(hour, weekday=0), [])


if __name__ == "__main__":
    unittest.main()
