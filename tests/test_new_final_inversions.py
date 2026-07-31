"""Test the 3 canonical final inversion rules (v83).

Rules:
  A — H3 Wednesday, D-sourced  → reverse
  B — H3 Thursday,  D-sourced  → reverse
  C — H16 Friday,   D-sourced  → reverse

No other inversion rules exist in v83.
"""
import unittest
from datetime import date
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestNewFinalInversions(unittest.TestCase):
    """Canonical 3-rule inversion set for v83."""

    def setUp(self):
        from mt5_signal_bot import apply_new_final_signal_inversion
        self.invert = apply_new_final_signal_inversion

    # === Rule A: H3 Wednesday, D-sourced ===

    def test_h3_wednesday_d_buy_to_sell(self):
        wed = date(2026, 7, 29)  # Wednesday
        result, rule = self.invert("BUY", wed, 3, "D_DIRECTION")
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "WEDNESDAY_H3_D_EXTRA_REVERSE")

    def test_h3_wednesday_d_sell_to_buy(self):
        wed = date(2026, 7, 29)
        result, rule = self.invert("SELL", wed, 3, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "WEDNESDAY_H3_D_EXTRA_REVERSE")

    def test_h3_wednesday_h1_no_invert(self):
        """H3 Wednesday with H1 source must NOT invert."""
        wed = date(2026, 7, 29)
        result, rule = self.invert("BUY", wed, 3, "PREVIOUS_COMPLETED_H1")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    # === Rule B: H3 Thursday, D-sourced ===

    def test_h3_thursday_d_sell_to_buy(self):
        thu = date(2026, 7, 30)  # Thursday
        result, rule = self.invert("SELL", thu, 3, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "THURSDAY_H3_D_EXTRA_REVERSE")

    def test_h3_thursday_d_buy_to_sell(self):
        thu = date(2026, 7, 30)
        result, rule = self.invert("BUY", thu, 3, "D_DIRECTION")
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "THURSDAY_H3_D_EXTRA_REVERSE")

    def test_h3_thursday_h1_no_invert(self):
        """H3 Thursday with H1 source must NOT invert."""
        thu = date(2026, 7, 30)
        result, rule = self.invert("BUY", thu, 3, "PREVIOUS_COMPLETED_H1")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    # === Rule C: H16 Friday, D-sourced ===

    def test_h16_friday_d_buy_to_sell(self):
        fri = date(2026, 7, 31)  # Friday
        result, rule = self.invert("BUY", fri, 16, "D_DIRECTION")
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "FRIDAY_H16_D_EXTRA_REVERSE")

    def test_h16_friday_d_sell_to_buy(self):
        fri = date(2026, 7, 31)
        result, rule = self.invert("SELL", fri, 16, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "FRIDAY_H16_D_EXTRA_REVERSE")

    def test_h16_friday_h1_no_invert(self):
        """H16 Friday with H1 source must NOT invert (rule only for D)."""
        fri = date(2026, 7, 31)
        result, rule = self.invert("BUY", fri, 16, "PREVIOUS_COMPLETED_H1")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    # === Explicit NO-INVERSION cases (old v82 rules removed in v83) ===

    def test_h14_tuesday_no_invert(self):
        """v83: H14 Tuesday must NOT invert (rule removed)."""
        tue = date(2026, 7, 28)
        result, rule = self.invert("BUY", tue, 14, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_h14_wednesday_no_invert(self):
        """v83: H14 Wednesday must NOT invert (rule removed)."""
        wed = date(2026, 7, 29)
        result, rule = self.invert("SELL", wed, 14, "D_DIRECTION")
        self.assertEqual(result, "SELL")
        self.assertIsNone(rule)

    def test_h16_tuesday_no_invert(self):
        """v83: H16 Tuesday must NOT invert (rule removed)."""
        tue = date(2026, 7, 28)
        result, rule = self.invert("BUY", tue, 16, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_h16_wednesday_no_invert(self):
        """v83: H16 Wednesday must NOT invert (rule removed)."""
        wed = date(2026, 7, 29)
        result, rule = self.invert("SELL", wed, 16, "D_DIRECTION")
        self.assertEqual(result, "SELL")
        self.assertIsNone(rule)

    def test_h16_monday_no_invert(self):
        mon = date(2026, 7, 27)  # Monday
        result, rule = self.invert("BUY", mon, 16, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_h16_thursday_no_invert(self):
        thu = date(2026, 7, 30)
        result, rule = self.invert("BUY", thu, 16, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_friday_h3_no_invert(self):
        """Friday H3 must NOT auto-invert."""
        fri = date(2026, 7, 31)
        result, rule = self.invert("BUY", fri, 3, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_friday_h7_no_invert(self):
        fri = date(2026, 7, 31)
        result, rule = self.invert("BUY", fri, 7, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_friday_h12_no_invert(self):
        fri = date(2026, 7, 31)
        result, rule = self.invert("BUY", fri, 12, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_friday_h14_no_invert(self):
        fri = date(2026, 7, 31)
        result, rule = self.invert("BUY", fri, 14, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_monday_h16_no_invert(self):
        """Monday H16 must NOT invert."""
        mon = date(2026, 7, 27)
        result, rule = self.invert("BUY", mon, 16, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_wait_not_inverted(self):
        wed = date(2026, 7, 29)
        result, rule = self.invert("WAIT", wed, 3, "D_DIRECTION")
        self.assertEqual(result, "WAIT")
        self.assertIsNone(rule)


class TestRemovedLegacyInversions(unittest.TestCase):
    """Verify legacy inversion functions are no longer in active production code."""

    def test_no_friday_d_action(self):
        """friday_d_action should not be importable from the active code path."""
        import mt5_signal_bot as bot
        self.assertFalse(hasattr(bot, "friday_d_action"),
                         "friday_d_action should be removed from active code")

    def test_no_resolve_h16_d_action(self):
        import mt5_signal_bot as bot
        self.assertFalse(hasattr(bot, "resolve_h16_d_action"),
                         "resolve_h16_d_action should be removed from active code")


if __name__ == "__main__":
    unittest.main()
