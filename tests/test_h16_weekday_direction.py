"""Legacy H16 weekday direction tests — replaced by test_new_final_inversions.py (v82).

The old friday_d_action and resolve_h16_d_action functions have been removed.
H16 now uses the same Pair Day Mode matrix + new final inversion rules.
"""
import unittest
import warnings

class TestLegacyH16WeekdayDirection(unittest.TestCase):
    """All legacy H16 weekday tests are superseded by v82 rules."""

    def test_legacy_functions_removed(self):
        """Verify friday_d_action and resolve_h16_d_action are no longer in the module."""
        import mt5_signal_bot as bot
        self.assertFalse(hasattr(bot, "friday_d_action"))
        self.assertFalse(hasattr(bot, "resolve_h16_d_action"))


if __name__ == "__main__":
    unittest.main()
