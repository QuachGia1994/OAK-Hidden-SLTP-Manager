"""v84 weekday slot inversion tests.

v84 rules (via apply_weekday_slot_inversion legacy wrapper):
  A — H3 Wednesday / Thursday, D-sourced
  B — H16 Tuesday / Wednesday / Friday, D-sourced
  C — H14 Tuesday / Wednesday, Always
"""

import unittest
from datetime import date

from mt5_signal_bot import apply_weekday_slot_inversion


class LegacyWeekdaySlotInversionTests(unittest.TestCase):
    """Tests via the legacy wrapper — validates v84 rule names."""

    def test_wednesday_h3_reverses_buy(self):
        wed = date(2026, 7, 29)
        result, rule = apply_weekday_slot_inversion("BUY", wed, 3)
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H3_WEDNESDAY")

    def test_thursday_h3_reverses_buy(self):
        thu = date(2026, 7, 30)
        result, rule = apply_weekday_slot_inversion("BUY", thu, 3)
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H3_THURSDAY")

    def test_friday_h16_reverses(self):
        fri = date(2026, 7, 31)
        result, rule = apply_weekday_slot_inversion("BUY", fri, 16)
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H16_FRIDAY_NORMAL")

    def test_tuesday_h16_reverses(self):
        tue = date(2026, 7, 28)
        result, rule = apply_weekday_slot_inversion("BUY", tue, 16)
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H16_TUESDAY")

    def test_wednesday_h16_reverses(self):
        wed = date(2026, 7, 29)
        result, rule = apply_weekday_slot_inversion("SELL", wed, 16)
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "H16_WEDNESDAY")

    def test_wednesday_h14_reverses(self):
        wed = date(2026, 7, 29)
        result, rule = apply_weekday_slot_inversion("BUY", wed, 14)
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H14_WEDNESDAY")

    def test_tuesday_h14_reverses(self):
        tue = date(2026, 7, 28)
        result, rule = apply_weekday_slot_inversion("SELL", tue, 14)
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "H14_TUESDAY")

    def test_wednesday_h12_no_inversion(self):
        wed = date(2026, 7, 29)
        result, rule = apply_weekday_slot_inversion("BUY", wed, 12)
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_friday_h3_no_inversion(self):
        fri = date(2026, 7, 31)
        result, rule = apply_weekday_slot_inversion("BUY", fri, 3)
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)


if __name__ == "__main__":
    unittest.main()
