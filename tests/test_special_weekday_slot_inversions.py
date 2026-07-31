"""v83 weekday slot inversion tests — validates 3-rule canonical set.

v83 rules (via apply_weekday_slot_inversion legacy wrapper):
  A — H3 Wednesday, D-sourced  → WEDNESDAY_H3_D_EXTRA_REVERSE
  B — H3 Thursday,  D-sourced  → THURSDAY_H3_D_EXTRA_REVERSE
  C — H16 Friday,   D-sourced  → FRIDAY_H16_D_EXTRA_REVERSE

Removed in v83:
  H14_TUE_WED_EXTRA_REVERSE (both days)
  H16_TUE_WED_FRI ... Tuesday and Wednesday cases
"""

import unittest
from datetime import date

from mt5_signal_bot import apply_weekday_slot_inversion


class LegacyWeekdaySlotInversionTests(unittest.TestCase):
    """Tests via the legacy wrapper — validates v83 rule names."""

    # ---- Rules PRESENT in v83 ----

    def test_wednesday_h3_reverses_buy(self):
        """Wednesday H3 D-sourced IS inverted in v83 (Rule A)."""
        wed = date(2026, 7, 29)
        result, rule = apply_weekday_slot_inversion("BUY", wed, 3)
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "WEDNESDAY_H3_D_EXTRA_REVERSE")

    def test_wednesday_h3_reverses_sell(self):
        wed = date(2026, 7, 29)
        result, rule = apply_weekday_slot_inversion("SELL", wed, 3)
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "WEDNESDAY_H3_D_EXTRA_REVERSE")

    def test_thursday_h3_reverses_buy(self):
        """Thursday H3 D-sourced IS inverted in v83 (Rule B)."""
        thu = date(2026, 7, 30)
        result, rule = apply_weekday_slot_inversion("BUY", thu, 3)
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "THURSDAY_H3_D_EXTRA_REVERSE")

    def test_friday_h16_reverses(self):
        """Friday H16 IS inverted in v83 (Rule C)."""
        fri = date(2026, 7, 31)
        result, rule = apply_weekday_slot_inversion("BUY", fri, 16)
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "FRIDAY_H16_D_EXTRA_REVERSE")

    def test_friday_h16_reverses_sell(self):
        fri = date(2026, 7, 31)
        result, rule = apply_weekday_slot_inversion("SELL", fri, 16)
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "FRIDAY_H16_D_EXTRA_REVERSE")

    # ---- Rules REMOVED in v83 (must NOT invert) ----

    def test_wednesday_h14_no_longer_reverses_buy(self):
        """v83: H14 Wednesday must NOT invert (rule removed)."""
        wed = date(2026, 7, 29)
        result, rule = apply_weekday_slot_inversion("BUY", wed, 14)
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_wednesday_h14_no_longer_reverses_sell(self):
        wed = date(2026, 7, 29)
        result, rule = apply_weekday_slot_inversion("SELL", wed, 14)
        self.assertEqual(result, "SELL")
        self.assertIsNone(rule)

    def test_wednesday_h12_no_inversion(self):
        wed = date(2026, 7, 29)
        result, rule = apply_weekday_slot_inversion("BUY", wed, 12)
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_tuesday_h14_no_longer_reverses(self):
        """v83: H14 Tuesday must NOT invert (rule removed)."""
        tue = date(2026, 7, 28)
        result, rule = apply_weekday_slot_inversion("SELL", tue, 14)
        self.assertEqual(result, "SELL")
        self.assertIsNone(rule)

    def test_tuesday_h16_no_longer_reverses(self):
        """v83: H16 Tuesday must NOT invert (rule removed)."""
        tue = date(2026, 7, 28)
        result, rule = apply_weekday_slot_inversion("BUY", tue, 16)
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_friday_h3_no_longer_reverses(self):
        """Friday H3 is NOT inverted in v83."""
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


if __name__ == "__main__":
    unittest.main()
