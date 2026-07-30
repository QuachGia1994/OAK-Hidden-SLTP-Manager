"""Wednesday H14 and Friday H3/H7/H12/H14 extra inversions (v80)."""

import unittest
from datetime import date

from mt5_signal_bot import apply_weekday_slot_inversion


class WeekdaySlotInversionTests(unittest.TestCase):
    def test_wednesday_h14_reverses_buy(self):
        # Wednesday = weekday 2
        wed = date(2026, 7, 29)
        self.assertEqual(wed.weekday(), 2)
        result, rule = apply_weekday_slot_inversion("BUY", wed, 14)
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "WEDNESDAY_H14_EXTRA_REVERSE")

    def test_wednesday_h14_reverses_sell(self):
        wed = date(2026, 7, 29)
        result, rule = apply_weekday_slot_inversion("SELL", wed, 14)
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "WEDNESDAY_H14_EXTRA_REVERSE")

    def test_wednesday_h12_no_inversion(self):
        wed = date(2026, 7, 29)
        result, rule = apply_weekday_slot_inversion("BUY", wed, 12)
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_friday_h3_reverses(self):
        fri = date(2026, 7, 31)
        self.assertEqual(fri.weekday(), 4)
        result, rule = apply_weekday_slot_inversion("BUY", fri, 3)
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "FRIDAY_H3_H7_H12_H14_EXTRA_REVERSE")

    def test_friday_h7_reverses(self):
        fri = date(2026, 7, 31)
        result, rule = apply_weekday_slot_inversion("SELL", fri, 7)
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "FRIDAY_H3_H7_H12_H14_EXTRA_REVERSE")

    def test_friday_h12_reverses(self):
        fri = date(2026, 7, 31)
        result, rule = apply_weekday_slot_inversion("BUY", fri, 12)
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "FRIDAY_H3_H7_H12_H14_EXTRA_REVERSE")

    def test_friday_h14_reverses(self):
        fri = date(2026, 7, 31)
        result, rule = apply_weekday_slot_inversion("SELL", fri, 14)
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "FRIDAY_H3_H7_H12_H14_EXTRA_REVERSE")

    def test_friday_h9_no_inversion(self):
        """Friday H9 is NOT inverted."""
        fri = date(2026, 7, 31)
        result, rule = apply_weekday_slot_inversion("BUY", fri, 9)
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_friday_h16_no_inversion(self):
        """Friday H16 is NOT inverted."""
        fri = date(2026, 7, 31)
        result, rule = apply_weekday_slot_inversion("BUY", fri, 16)
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_thursday_no_inversion(self):
        thu = date(2026, 7, 30)
        self.assertEqual(thu.weekday(), 3)
        result, rule = apply_weekday_slot_inversion("BUY", thu, 14)
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_wait_not_inverted(self):
        wed = date(2026, 7, 29)
        result, rule = apply_weekday_slot_inversion("WAIT", wed, 14)
        self.assertEqual(result, "WAIT")
        self.assertIsNone(rule)


if __name__ == "__main__":
    unittest.main()
