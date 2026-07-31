"""Test the canonical final inversion rules (v84).

Rules:
  A — H3 Wed/Thu, D-sourced → reverse
  B — H16 Tue/Wed/Fri, D-sourced → reverse
  C — H14 Tue/Wed, ALWAYS → reverse
"""
import unittest
from datetime import date
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestNewFinalInversions(unittest.TestCase):
    """Canonical inversion set for v84."""

    def setUp(self):
        from mt5_signal_bot import apply_new_final_signal_inversion
        self.invert = apply_new_final_signal_inversion

    # === Rule A: H3 Wednesday/Thursday, D-sourced ===

    def test_h3_wednesday_d_buy_to_sell(self):
        wed = date(2026, 7, 29)  # Wednesday
        result, rule = self.invert("BUY", wed, 3, "D_DIRECTION")
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H3_WEDNESDAY")

    def test_h3_thursday_d_sell_to_buy(self):
        thu = date(2026, 7, 30)  # Thursday
        result, rule = self.invert("SELL", thu, 3, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "H3_THURSDAY")

    def test_h3_wednesday_h1_inverts_in_v86(self):
        wed = date(2026, 7, 29)
        result, rule = self.invert("BUY", wed, 3, "PREVIOUS_COMPLETED_H1")
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H3_WEDNESDAY")

    # === Rule B: H16 Tue/Wed/Fri ===

    def test_h16_tuesday_d_inverts(self):
        tue = date(2026, 7, 28)
        result, rule = self.invert("BUY", tue, 16, "D_DIRECTION")
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H16_TUESDAY")

    def test_h16_wednesday_d_inverts(self):
        wed = date(2026, 7, 29)
        result, rule = self.invert("SELL", wed, 16, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "H16_WEDNESDAY")

    def test_h16_friday_d_inverts(self):
        fri = date(2026, 7, 31)
        result, rule = self.invert("BUY", fri, 16, "D_DIRECTION")
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H16_FRIDAY_NORMAL")

    def test_h16_tuesday_h1_inverts_in_v86(self):
        tue = date(2026, 7, 28)
        result, rule = self.invert("BUY", tue, 16, "PREVIOUS_COMPLETED_H1")
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H16_TUESDAY")

    # === Rule C: H14 Tuesday/Wednesday, Always ===

    def test_h14_tuesday_always_inverts(self):
        tue = date(2026, 7, 28)
        result, rule = self.invert("BUY", tue, 14, "D_DIRECTION")
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H14_TUESDAY")

    def test_h14_wednesday_always_inverts(self):
        wed = date(2026, 7, 29)
        result, rule = self.invert("SELL", wed, 14, "PREVIOUS_COMPLETED_H1")
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "H14_WEDNESDAY")

    # === No-inversion cases ===

    def test_h16_monday_no_invert(self):
        mon = date(2026, 7, 27)
        result, rule = self.invert("BUY", mon, 16, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_h16_thursday_no_invert(self):
        thu = date(2026, 7, 30)
        result, rule = self.invert("BUY", thu, 16, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)


if __name__ == "__main__":
    unittest.main()
