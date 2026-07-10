# -*- coding: utf-8 -*-
"""No-gold LABEL + Focus rules: T5 H=3-4+H≥12; T6 H=3-11; Fri focus narrow."""
import unittest
from datetime import datetime

from mt5_signal_bot import (
    is_xau_no_trade_label_slot,
    is_thursday_no_gold_slot,
    xau_no_trade_label_tag,
    thursday_no_gold_label,
    get_hour_note,
    get_focus_gbp_pairs,
    get_pair_direction,
    format_telegram_pair_block,
)
from oak_trading_reminders import get_day_notes


class TestXauNoTradeLabel(unittest.TestCase):
    def test_t5_h3_h4(self):
        thu = datetime(2026, 7, 9, 10, 0)  # Thursday
        mon = datetime(2026, 7, 6, 10, 0)  # Monday
        for h in (3, 4):
            self.assertTrue(is_xau_no_trade_label_slot(h, thu), h)
            self.assertFalse(is_xau_no_trade_label_slot(h, mon), h)
            self.assertEqual(xau_no_trade_label_tag(h, thu), "H=3-4")

    def test_t6_h3_to_h11(self):
        fri = datetime(2026, 7, 10, 10, 0)  # Friday
        for h in range(3, 12):
            self.assertTrue(is_xau_no_trade_label_slot(h, fri), h)
            self.assertEqual(xau_no_trade_label_tag(h, fri), "T6 H=3-11")
        # H=12-15 Gold normal on Friday
        for h in (12, 15):
            self.assertFalse(is_xau_no_trade_label_slot(h, fri), h)
            self.assertEqual(xau_no_trade_label_tag(h, fri), "")

    def test_t5_h12_plus(self):
        thu = datetime(2026, 7, 9, 13, 0)
        fri = datetime(2026, 7, 10, 13, 0)
        self.assertTrue(is_xau_no_trade_label_slot(12, thu))
        self.assertTrue(is_xau_no_trade_label_slot(15, thu))
        self.assertFalse(is_xau_no_trade_label_slot(12, fri))
        self.assertEqual(xau_no_trade_label_tag(15, thu), "T5 H≥12")

    def test_alias(self):
        self.assertTrue(is_thursday_no_gold_slot(12, weekday=3))
        self.assertTrue(is_thursday_no_gold_slot(5, weekday=4))  # Fri H=5
        self.assertTrue(is_thursday_no_gold_slot(9, weekday=4))  # Fri H=9 no-gold
        self.assertTrue(is_thursday_no_gold_slot(11, weekday=4))  # Fri H=11 no-gold
        self.assertFalse(is_thursday_no_gold_slot(12, weekday=4))  # Fri H=12 gold OK

    def test_telegram_block_h3(self):
        block = format_telegram_pair_block(
            {"XAUUSD": "BUY", "GBPAUD": "SELL", "GBPJPY": "SELL"},
            3,
            weekday=3,
        )
        self.assertIn("KHÔNG ĐÁNH", block)
        self.assertIn("H=3-4", block)
        self.assertIn("ngược Vàng", block)
        self.assertIn("GBPAUD", block)
        self.assertIn("GBPJPY", block)
        self.assertNotIn("cùng Vàng", block)
        self.assertNotIn("GBPAUD: SELL", block)

    def test_telegram_block_fri_h9(self):
        block = format_telegram_pair_block(
            {"XAUUSD": "BUY"},
            9,
            weekday=4,
        )
        self.assertIn("KHÔNG ĐÁNH", block)
        self.assertIn("T6 H=3-11", block)
        self.assertIn("GBPAUD", block)
        self.assertIn("GBPJPY", block)
        self.assertNotIn("GBPUSD", block)
        self.assertNotIn("GBPCAD", block)

    def test_hour_note_h3_h4_relation(self):
        for h in (3, 4):
            note = get_hour_note(h, weekday=4)
            self.assertIn("ngược Vàng", note)
            self.assertIn("GBPAUD", note)
            self.assertIn("GBPJPY", note)
            self.assertNotIn("cùng Vàng", note)
            self.assertNotIn("KHÔNG đánh Vàng", note)
        note5 = get_hour_note(5, weekday=4)
        self.assertNotIn("ngược Vàng", note5)
        self.assertIn("GBPAUD", note5)
        self.assertIn("không GBPJPY", note5)

    def test_label_en(self):
        self.assertIn("NO Gold", thursday_no_gold_label("EN"))

    def test_day_notes_include_slots(self):
        notes = get_day_notes(datetime(2026, 7, 9), lang="VN")
        blob = " ".join(notes)
        self.assertIn("H=3-13,15", blob)
        self.assertIn("H=3-4", blob)
        notes_fri = get_day_notes(datetime(2026, 7, 10), lang="VN")
        blob_f = " ".join(notes_fri)
        self.assertIn("H=3-11", blob_f)
        self.assertIn("H=12,15", blob_f)


class TestFocusGbpPairs(unittest.TestCase):
    def test_h3_h4_ga_gj(self):
        for wd in (0, 1, 2, 3, 4):
            for h in (3, 4):
                self.assertEqual(
                    get_focus_gbp_pairs(h, weekday=wd),
                    ["GBPAUD", "GBPJPY"],
                    (wd, h),
                )

    def test_h5_h8_focus_ga_only(self):
        for wd in (0, 1, 2, 3, 4):
            for h in range(5, 9):
                self.assertEqual(
                    get_focus_gbp_pairs(h, weekday=wd),
                    ["GBPAUD"],
                    (wd, h),
                )

    def test_h9_full_group_mon_thu(self):
        full = ["GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"]
        for wd in (0, 1, 2, 3):
            for h in (9, 11, 12, 15):
                self.assertEqual(get_focus_gbp_pairs(h, weekday=wd), full, (wd, h))

    def test_h9_fri_only_ga_gj(self):
        for h in (9, 11, 12, 15):
            self.assertEqual(
                get_focus_gbp_pairs(h, weekday=4),
                ["GBPAUD", "GBPJPY"],
                h,
            )

    def test_h14_disabled_no_focus(self):
        """H=14 slot removed — no focus pairs."""
        for wd in (0, 1, 2, 3, 4):
            self.assertEqual(get_focus_gbp_pairs(14, weekday=wd), [])

    def test_h15_pair_dirs_xau_only(self):
        """H=15: only XAUUSD in pair_dirs (Focus list separate)."""
        mon = datetime(2026, 7, 6, 15, 0)
        dirs = get_pair_direction(15, "BUY", mon)
        self.assertEqual(dirs.get("XAUUSD"), "BUY")
        for p in ("GBPAUD", "GBPCAD", "GBPUSD", "GBPJPY"):
            self.assertNotIn(p, dirs, p)


if __name__ == "__main__":
    unittest.main()
