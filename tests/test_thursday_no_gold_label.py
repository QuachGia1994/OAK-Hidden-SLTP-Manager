# -*- coding: utf-8 -*-
"""Schedule rules for no-gold labels and Friday gold reversal notes."""
import unittest
from datetime import datetime

from mt5_signal_bot import (
    analyze,
    format_telegram_pair_block,
    get_focus_gbp_pairs,
    get_hour_note,
    get_pair_direction,
    is_xau_no_trade_label_slot,
    xau_no_trade_label_tag,
)


class TestThursdayAndFridayRules(unittest.TestCase):
    def test_thursday_h3_h4_and_h12_plus_are_no_gold(self):
        thursday = datetime(2026, 7, 9, 13, 0)
        for hour in (3, 4):
            self.assertTrue(is_xau_no_trade_label_slot(hour, thursday))
            self.assertEqual(xau_no_trade_label_tag(hour, thursday), "T5 H=3-4")
        for hour in (12, 13, 14, 15):
            self.assertTrue(is_xau_no_trade_label_slot(hour, thursday))
            self.assertEqual(xau_no_trade_label_tag(hour, thursday), "T5 H>=12")
        for hour in (5, 6, 7, 8, 9, 10, 11):
            self.assertFalse(is_xau_no_trade_label_slot(hour, thursday))
            self.assertEqual(xau_no_trade_label_tag(hour, thursday), "")

    def test_tuesday_and_wednesday_have_h9_to_h11_no_gold(self):
        for weekday in (1, 2):
            for hour in (9, 10, 11):
                with self.subTest(weekday=weekday, hour=hour):
                    self.assertTrue(is_xau_no_trade_label_slot(hour, weekday=weekday))
                    self.assertEqual(xau_no_trade_label_tag(hour, weekday=weekday), "T3/T4 H=9-11")

    def test_friday_has_no_gbp_focus(self):
        for hour in range(3, 16):
            self.assertEqual(get_focus_gbp_pairs(hour, weekday=4), [])
        self.assertEqual(get_hour_note(3, weekday=4), "Đảo signal ra Vàng (XAUUSD)")
        self.assertEqual(get_hour_note(7, weekday=4), "Đảo signal ra Vàng (XAUUSD)")
        self.assertEqual(get_hour_note(9, weekday=4), "Đảo signal ra Vàng (XAUUSD)")
        self.assertEqual(get_hour_note(10, weekday=4), "Đảo signal ra Vàng (XAUUSD)")
        self.assertEqual(get_hour_note(11, weekday=4), "Chỉ Vàng (XAUUSD)")
        self.assertEqual(get_hour_note(14, weekday=4), "Chỉ Vàng (XAUUSD)")
        for hour in range(3, 16):
            self.assertFalse(is_xau_no_trade_label_slot(hour, weekday=4))
            self.assertEqual(xau_no_trade_label_tag(hour, weekday=4), "")

    def test_h2_note_reverses_tuesday_and_regular_thursday_only(self):
        self.assertEqual(
            get_hour_note(2, broker_dt=datetime(2026, 7, 7, 2, 45)),
            "Đảo signal ra Vàng (XAUUSD)",
        )
        self.assertEqual(
            get_hour_note(2, broker_dt=datetime(2026, 7, 9, 2, 45)),
            "Đảo signal ra Vàng (XAUUSD)",
        )
        self.assertEqual(
            get_hour_note(2, broker_dt=datetime(2025, 5, 1, 2, 45)),
            "Chỉ Vàng (XAUUSD)",
        )
        self.assertEqual(
            get_hour_note(2, broker_dt=datetime(2025, 1, 3, 2, 45)),
            "Đảo signal ra Vàng (XAUUSD)",
        )
        self.assertEqual(
            get_hour_note(2, broker_dt=datetime(2026, 7, 10, 2, 45)),
            "Chỉ Vàng (XAUUSD)",
        )

    def test_friday_signal_is_reversed_in_analysis(self):
        from unittest.mock import patch
        import mt5_signal_bot

        candle = {"open": 1.0, "close": 2.0, "high": 2.0, "low": 1.0}
        friday = datetime(2026, 7, 10, 9, 0)
        with patch.object(mt5_signal_bot, "get_candle_by_ts", return_value=candle):
            result = analyze(friday, 3)
        self.assertEqual(result["signal"], "SELL")

    def test_friday_telegram_block_omits_gbp(self):
        block = format_telegram_pair_block({"XAUUSD": "BUY"}, 9, weekday=4)
        self.assertNotIn("KHÔNG ĐÁNH", block)
        self.assertIn("XAUUSD: Mua BUY", block)
        self.assertNotIn("GBP", block)

    def test_thursday_focus_schedule(self):
        thursday = datetime(2026, 7, 9, 12, 0)
        for hour in (3, 4):
            self.assertEqual(get_focus_gbp_pairs(hour, weekday=3), [])
            self.assertEqual(get_hour_note(hour, weekday=3), "Chỉ Vàng (XAUUSD)")
            result = get_pair_direction(hour, "BUY", thursday)
            self.assertEqual(result["XAUUSD"], "BUY")
            if hour == 4:
                self.assertEqual(result["D-DIRECTION"], "BUY")
            else:
                self.assertEqual(result, {"XAUUSD": "BUY"})
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
            self.assertEqual(get_focus_gbp_pairs(14, weekday=weekday), [])

    def test_monday_rule(self):
        self.assertEqual(get_hour_note(2, weekday=0), "Chỉ Vàng (XAUUSD)")
        for hour in range(3, 16):
            self.assertTrue(is_xau_no_trade_label_slot(hour, weekday=0))
            self.assertEqual(xau_no_trade_label_tag(hour, weekday=0), "T2 H=3-15")
        self.assertEqual(get_focus_gbp_pairs(2, weekday=0), [])
        self.assertEqual(get_focus_gbp_pairs(9, weekday=0), ["GBPUSD", "GBPCAD"])
        for hour in (3, 4, 5, 8, 10, 11, 12, 14, 15):
            self.assertEqual(get_focus_gbp_pairs(hour, weekday=0), [])
            self.assertEqual(get_hour_note(hour, weekday=0), "Chỉ Vàng (XAUUSD)")
        self.assertEqual(get_hour_note(9, weekday=0), "Chỉ Focus GBPUSD · GBPCAD")

    def test_monday_telegram_no_gold_block_does_not_show_gbpaud_focus(self):
        block = format_telegram_pair_block({"XAUUSD": "BUY"}, 5, weekday=0)
        self.assertIn("KHÔNG ĐÁNH", block)
        self.assertNotIn("GBPAUD", block)
        self.assertNotIn("Cặp GBP tập trung", block)


if __name__ == "__main__":
    unittest.main()
