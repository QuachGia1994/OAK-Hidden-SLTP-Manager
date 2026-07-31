"""Test per-symbol Day Mode anchoring (v82)."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestPairDayModes(unittest.TestCase):
    """Each symbol has its own independent Day Mode."""

    def test_day_mode_anchoring_per_symbol(self):
        """Day mode anchors independently per symbol."""
        from mt5_signal_bot import DayMode, resolve_or_anchor_day_mode

        # XAUUSD: H3 entry 04:25 (H_PLUS_1_25) → mode H_PLUS_1_25
        dm, anchored = resolve_or_anchor_day_mode(None, 3, "04:25")
        self.assertTrue(anchored)
        self.assertEqual(dm.mode, "DAY_MODE_H_PLUS_1_25")
        self.assertEqual(dm.source_hour, 3)

        # GBPUSD: H3 entry 03:49 (H_49) → no anchor, stays None
        dm2, anchored2 = resolve_or_anchor_day_mode(None, 3, "03:49")
        self.assertFalse(anchored2)
        self.assertIsNone(dm2)

        # GBPUSD: H7 entry 07:11 (H_11) → mode H11 source H7
        dm3, anchored3 = resolve_or_anchor_day_mode(None, 7, "07:11")
        self.assertTrue(anchored3)
        self.assertEqual(dm3.mode, "DAY_MODE_H11")
        self.assertEqual(dm3.source_hour, 7)

        # GBPAUD: H3 entry 03:11 (H_11) → mode H11 source H3
        dm4, anchored4 = resolve_or_anchor_day_mode(None, 3, "03:11")
        self.assertTrue(anchored4)
        self.assertEqual(dm4.mode, "DAY_MODE_H11")
        self.assertEqual(dm4.source_hour, 3)

    def test_day_mode_preserved_after_anchor(self):
        """Once anchored, day mode cannot be re-anchored."""
        from mt5_signal_bot import DayMode, resolve_or_anchor_day_mode

        existing = DayMode(mode="DAY_MODE_H11", source_hour=3,
                           source_entry_time="03:11", source_branch="H_11")

        # H7 with H_PLUS_1_25 entry → must NOT override
        dm, anchored = resolve_or_anchor_day_mode(existing, 7, "07:49")
        self.assertFalse(anchored)
        self.assertEqual(dm.mode, "DAY_MODE_H11")
        self.assertEqual(dm.source_hour, 3)

    def test_three_different_modes(self):
        """Three symbols can have three completely different modes."""
        from mt5_signal_bot import DayMode

        xau_mode = DayMode(mode="DAY_MODE_H_PLUS_1_25", source_hour=3,
                           source_entry_time="04:25", source_branch="H_PLUS_1_25")
        gbp_mode = DayMode(mode="DAY_MODE_H11", source_hour=7,
                           source_entry_time="07:11", source_branch="H_11")
        aud_mode = DayMode(mode="DAY_MODE_H11", source_hour=3,
                           source_entry_time="03:11", source_branch="H_11")

        self.assertNotEqual(xau_mode.mode, gbp_mode.mode)
        self.assertEqual(gbp_mode.mode, aud_mode.mode)
        self.assertNotEqual(gbp_mode.source_hour, aud_mode.source_hour)


class TestH16PerSymbolInheritance(unittest.TestCase):
    """H16 entry inheritance runs independently per symbol."""

    def test_h16_per_symbol_scan(self):
        from mt5_signal_bot import resolve_h16_inherited_entry_for_symbol

        # XAU: H14 had H_11 entry → H16 = 16:11
        prior = {
            14: {
                "pair_entry_states": {"XAUUSD": "READY"},
                "pair_entry_times": {"XAUUSD": "14:11"},
            },
        }
        xau_h16 = resolve_h16_inherited_entry_for_symbol("XAUUSD", prior)
        self.assertEqual(xau_h16["entry_time"], "16:11")
        self.assertEqual(xau_h16["entry_source_branch"], "H_11")

    def test_h16_gbpusd_different_source(self):
        from mt5_signal_bot import resolve_h16_inherited_entry_for_symbol

        # GBPUSD: H14 had H_49 (skipped), H12 had H_PLUS_1_25
        prior = {
            14: {
                "pair_entry_states": {"GBPUSD": "READY"},
                "pair_entry_times": {"GBPUSD": "14:49"},
            },
            12: {
                "pair_entry_states": {"GBPUSD": "READY"},
                "pair_entry_times": {"GBPUSD": "13:25"},
            },
        }
        gbp_h16 = resolve_h16_inherited_entry_for_symbol("GBPUSD", prior)
        self.assertEqual(gbp_h16["entry_time"], "17:25")
        self.assertEqual(gbp_h16["entry_source_branch"], "H_PLUS_1_25")
        self.assertEqual(gbp_h16["entry_source_hour"], 12)

    def test_h16_no_prior_entry(self):
        from mt5_signal_bot import resolve_h16_inherited_entry_for_symbol

        prior = {}
        result = resolve_h16_inherited_entry_for_symbol("GBPAUD", prior)
        self.assertIsNone(result["entry_time"])
        self.assertEqual(result["entry_state"], "WAIT")
        self.assertEqual(result["failure_reason"], "NO_ELIGIBLE_PRIOR_ENTRY")


if __name__ == "__main__":
    unittest.main()
