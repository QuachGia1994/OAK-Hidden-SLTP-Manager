# -*- coding: utf-8 -*-
"""No-gold LABEL slots: T5/T6 H=3-4; T5 H≥12 (logic still computes XAU)."""
import unittest
from datetime import datetime

from mt5_signal_bot import (
    is_xau_no_trade_label_slot,
    is_thursday_no_gold_slot,
    xau_no_trade_label_tag,
    thursday_no_gold_label,
    get_hour_note,
    format_telegram_pair_block,
)
from oak_trading_reminders import get_day_notes


class TestXauNoTradeLabel(unittest.TestCase):
    def test_t5_t6_h3_h4(self):
        thu = datetime(2026, 7, 9, 10, 0)  # Thursday
        fri = datetime(2026, 7, 10, 10, 0)  # Friday
        mon = datetime(2026, 7, 6, 10, 0)  # Monday
        for h in (3, 4):
            self.assertTrue(is_xau_no_trade_label_slot(h, thu), h)
            self.assertTrue(is_xau_no_trade_label_slot(h, fri), h)
            self.assertFalse(is_xau_no_trade_label_slot(h, mon), h)
            self.assertEqual(xau_no_trade_label_tag(h, thu), "H=3-4")

    def test_t5_h12_plus(self):
        thu = datetime(2026, 7, 9, 13, 0)
        fri = datetime(2026, 7, 10, 13, 0)
        self.assertTrue(is_xau_no_trade_label_slot(12, thu))
        self.assertTrue(is_xau_no_trade_label_slot(15, thu))
        self.assertFalse(is_xau_no_trade_label_slot(12, fri))
        self.assertEqual(xau_no_trade_label_tag(15, thu), "T5 H≥12")

    def test_alias(self):
        self.assertTrue(is_thursday_no_gold_slot(12, weekday=3))
        self.assertTrue(is_thursday_no_gold_slot(3, weekday=4))

    def test_telegram_block_h3(self):
        block = format_telegram_pair_block(
            {"XAUUSD": "BUY", "GBPAUD": "SELL", "GBPJPY": "BUY"},
            3,
            weekday=3,
        )
        self.assertIn("KHÔNG ĐÁNH", block)
        self.assertIn("H=3-4", block)
        self.assertIn("Focus · ngược Vàng", block)
        self.assertIn("Focus · cùng Vàng", block)
        self.assertNotIn("GBPAUD: SELL", block)

    def test_hour_note_h3_h4_relation(self):
        for h in (3, 4):
            note = get_hour_note(h, weekday=4)
            self.assertIn("GBPAUD ngược Vàng", note)
            self.assertIn("GBPJPY cùng Vàng", note)
            self.assertNotIn("KHÔNG đánh Vàng", note)
        # H=5..8: không dùng note quan hệ H=3-4
        note5 = get_hour_note(5, weekday=4)
        self.assertNotIn("ngược Vàng", note5)
        self.assertIn("GBPAUD", note5)

    def test_label_en(self):
        self.assertIn("NO Gold", thursday_no_gold_label("EN"))

    def test_day_notes_include_slots(self):
        notes = get_day_notes(datetime(2026, 7, 9), lang="VN")
        blob = " ".join(notes)
        self.assertIn("H=3-15", blob)
        self.assertIn("H=3-4", blob)


if __name__ == "__main__":
    unittest.main()
