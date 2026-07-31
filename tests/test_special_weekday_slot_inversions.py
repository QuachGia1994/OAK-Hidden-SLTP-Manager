"""Legacy weekday slot inversion tests — replaced by test_new_final_inversions.py (v82).

The old WEDNESDAY_H14_EXTRA_REVERSE and FRIDAY_H3_H7_H12_H14_EXTRA_REVERSE rules
have been replaced by 3 new rules in v82:
- H3_WED_THU_D_EXTRA_REVERSE
- H14_TUE_WED_EXTRA_REVERSE
- H16_TUE_WED_FRI_D_EXTRA_REVERSE
"""

import unittest
from datetime import date

from mt5_signal_bot import apply_weekday_slot_inversion


class LegacyWeekdaySlotInversionTests(unittest.TestCase):
    """Updated tests using the v82 rule names via the legacy wrapper."""

    def test_wednesday_h14_reverses_buy(self):
        wed = date(2026, 7, 29)
        result, rule = apply_weekday_slot_inversion("BUY", wed, 14)
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H14_TUE_WED_EXTRA_REVERSE")

    def test_wednesday_h14_reverses_sell(self):
        wed = date(2026, 7, 29)
        result, rule = apply_weekday_slot_inversion("SELL", wed, 14)
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "H14_TUE_WED_EXTRA_REVERSE")

    def test_wednesday_h12_no_inversion(self):
        wed = date(2026, 7, 29)
        result, rule = apply_weekday_slot_inversion("BUY", wed, 12)
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_friday_h3_no_longer_reverses(self):
        """Friday H3 is NO LONGER inverted in v82."""
        fri = date(2026, 7, 31)
        result, rule = apply_weekday_slot_inversion("BUY", fri, 3)
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_friday_h7_no_longer_reverses(self):
        fri = date(2026, 7, 31)
        result, rule = apply_weekday_slot_inversion("SELL", fri, 7)
        self.assertEqual(result, "SELL")
        self.assertIsNone(rule)

    def test_friday_h12_no_longer_reverses(self):
        fri = date(2026, 7, 31)
        result, rule = apply_weekday_slot_inversion("BUY", fri, 12)
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_friday_h14_no_longer_reverses(self):
        fri = date(2026, 7, 31)
        result, rule = apply_weekday_slot_inversion("SELL", fri, 14)
        self.assertEqual(result, "SELL")
        self.assertIsNone(rule)

    def test_friday_h9_no_inversion(self):
        fri = date(2026, 7, 31)
        result, rule = apply_weekday_slot_inversion("BUY", fri, 9)
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_friday_h16_reverses(self):
        """Friday H16 IS inverted in v82 (new rule)."""
        fri = date(2026, 7, 31)
        result, rule = apply_weekday_slot_inversion("BUY", fri, 16)
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H16_TUE_WED_FRI_D_EXTRA_REVERSE")

    def test_wednesday_h3_reverses(self):
        """Wednesday H3 IS inverted in v82 (new rule)."""
        wed = date(2026, 7, 29)
        result, rule = apply_weekday_slot_inversion("BUY", wed, 3)
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H3_WED_THU_D_EXTRA_REVERSE")

    def test_tuesday_h14_reverses(self):
        """Tuesday H14 IS inverted in v82 (new rule)."""
        tue = date(2026, 7, 28)
        result, rule = apply_weekday_slot_inversion("SELL", tue, 14)
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "H14_TUE_WED_EXTRA_REVERSE")

    def test_tuesday_h16_reverses(self):
        """Tuesday H16 IS inverted in v82 (new rule)."""
        tue = date(2026, 7, 28)
        result, rule = apply_weekday_slot_inversion("BUY", tue, 16)
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H16_TUE_WED_FRI_D_EXTRA_REVERSE")


if __name__ == "__main__":
    unittest.main()
