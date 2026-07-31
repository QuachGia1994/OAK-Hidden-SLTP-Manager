"""Test the 3 new final inversion rules (v82)."""
import unittest
from datetime import date
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestNewFinalInversions(unittest.TestCase):
    """Only 3 final inversion rules exist in v82."""

    def setUp(self):
        from mt5_signal_bot import apply_new_final_signal_inversion
        self.invert = apply_new_final_signal_inversion

    # === Rule A: H3 Wed/Thu, D-based only ===

    def test_h3_wednesday_d_buy_to_sell(self):
        wed = date(2026, 7, 29)  # Wednesday
        result, rule = self.invert("BUY", wed, 3, "D_DIRECTION")
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H3_WED_THU_D_EXTRA_REVERSE")

    def test_h3_wednesday_d_sell_to_buy(self):
        wed = date(2026, 7, 29)
        result, rule = self.invert("SELL", wed, 3, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "H3_WED_THU_D_EXTRA_REVERSE")

    def test_h3_thursday_d_sell_to_buy(self):
        thu = date(2026, 7, 30)  # Thursday
        result, rule = self.invert("SELL", thu, 3, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "H3_WED_THU_D_EXTRA_REVERSE")

    def test_h3_wednesday_h1_no_invert(self):
        """H3 Wednesday with H1 source must NOT invert."""
        wed = date(2026, 7, 29)
        result, rule = self.invert("BUY", wed, 3, "PREVIOUS_COMPLETED_H1")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    # === Rule B: H16 Tue/Wed/Fri, D-based only ===

    def test_h16_tuesday_d_buy_to_sell(self):
        tue = date(2026, 7, 28)  # Tuesday
        result, rule = self.invert("BUY", tue, 16, "D_DIRECTION")
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H16_TUE_WED_FRI_D_EXTRA_REVERSE")

    def test_h16_wednesday_d_sell_to_buy(self):
        wed = date(2026, 7, 29)
        result, rule = self.invert("SELL", wed, 16, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "H16_TUE_WED_FRI_D_EXTRA_REVERSE")

    def test_h16_friday_d_buy_to_sell(self):
        fri = date(2026, 7, 31)  # Friday
        result, rule = self.invert("BUY", fri, 16, "D_DIRECTION")
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H16_TUE_WED_FRI_D_EXTRA_REVERSE")

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

    def test_h16_tuesday_h1_no_invert(self):
        tue = date(2026, 7, 28)
        result, rule = self.invert("BUY", tue, 16, "PREVIOUS_COMPLETED_H1")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    # === Rule C: H14 Tue/Wed, always invert ===

    def test_h14_tuesday_d_buy_to_sell(self):
        tue = date(2026, 7, 28)
        result, rule = self.invert("BUY", tue, 14, "D_DIRECTION")
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H14_TUE_WED_EXTRA_REVERSE")

    def test_h14_tuesday_h1_sell_to_buy(self):
        tue = date(2026, 7, 28)
        result, rule = self.invert("SELL", tue, 14, "PREVIOUS_COMPLETED_H1")
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "H14_TUE_WED_EXTRA_REVERSE")

    def test_h14_wednesday_d_sell_to_buy(self):
        wed = date(2026, 7, 29)
        result, rule = self.invert("SELL", wed, 14, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertEqual(rule, "H14_TUE_WED_EXTRA_REVERSE")

    def test_h14_wednesday_h1_buy_to_sell(self):
        wed = date(2026, 7, 29)
        result, rule = self.invert("BUY", wed, 14, "PREVIOUS_COMPLETED_H1")
        self.assertEqual(result, "SELL")
        self.assertEqual(rule, "H14_TUE_WED_EXTRA_REVERSE")

    # === No other inversions ===

    def test_friday_h3_no_invert(self):
        """Friday H3 must NOT auto-invert (old rule removed)."""
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

    def test_monday_h16_no_friday_rule(self):
        """Monday H16 must NOT use previous-Friday rule."""
        mon = date(2026, 7, 27)
        result, rule = self.invert("BUY", mon, 16, "D_DIRECTION")
        self.assertEqual(result, "BUY")
        self.assertIsNone(rule)

    def test_thursday_h16_no_special_dates(self):
        """Thursday H16 must NOT have day-30/day-1 rule."""
        thu = date(2026, 7, 30)
        result, rule = self.invert("SELL", thu, 16, "D_DIRECTION")
        self.assertEqual(result, "SELL")
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
