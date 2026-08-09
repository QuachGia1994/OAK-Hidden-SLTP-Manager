"""DayMode anchoring: first H:11 or (H+1):25 anchors; H:49 never anchors."""

import unittest
from mt5_signal_bot import (
    DayMode,
    classify_slot_entry_branch,
    resolve_or_anchor_day_mode,
)


class ClassifySlotEntryBranchTests(unittest.TestCase):
    def test_h11_branch(self):
        self.assertEqual(classify_slot_entry_branch(3, "03:11"), "H_11")
        self.assertEqual(classify_slot_entry_branch(7, "07:11"), "H_11")
        self.assertEqual(classify_slot_entry_branch(12, "12:11"), "H_11")

    def test_h49_branch(self):
        self.assertEqual(classify_slot_entry_branch(3, "03:49"), "H_49")
        self.assertEqual(classify_slot_entry_branch(7, "07:49"), "H_49")
        self.assertEqual(classify_slot_entry_branch(14, "14:49"), "H_49")

    def test_h_plus_1_25_branch(self):
        self.assertEqual(classify_slot_entry_branch(7, "08:25"), "H_PLUS_1_25")
        self.assertEqual(classify_slot_entry_branch(12, "13:25"), "H_PLUS_1_25")

    def test_h3_bt_special_0425(self):
        self.assertEqual(classify_slot_entry_branch(3, "04:25"), "H_PLUS_1_25")

    def test_none_entry(self):
        self.assertIsNone(classify_slot_entry_branch(3, None))
        self.assertIsNone(classify_slot_entry_branch(3, ""))


class DayModeAnchorTests(unittest.TestCase):
    def test_h3_0311_anchors_day_mode_h11(self):
        mode, anchored = resolve_or_anchor_day_mode(None, 3, "03:11")
        self.assertTrue(anchored)
        self.assertEqual(mode.mode, "DAY_MODE_H11")
        self.assertEqual(mode.source_hour, 3)
        self.assertEqual(mode.source_branch, "H_11")

    def test_h3_0425_anchors_day_mode_h_plus_1_25(self):
        mode, anchored = resolve_or_anchor_day_mode(None, 3, "04:25")
        self.assertTrue(anchored)
        self.assertEqual(mode.mode, "DAY_MODE_H_PLUS_1_25")
        self.assertEqual(mode.source_hour, 3)
        self.assertEqual(mode.source_branch, "H_PLUS_1_25")

    def test_h49_never_anchors(self):
        mode, anchored = resolve_or_anchor_day_mode(None, 3, "03:49")
        self.assertFalse(anchored)
        self.assertIsNone(mode)

    def test_h3_h49_then_h7_h11_anchors_at_h7(self):
        # H3 03:49 → no anchor
        mode, anchored = resolve_or_anchor_day_mode(None, 3, "03:49")
        self.assertFalse(anchored)
        self.assertIsNone(mode)
        # H7 07:11 → anchors
        mode, anchored = resolve_or_anchor_day_mode(mode, 7, "07:11")
        self.assertTrue(anchored)
        self.assertEqual(mode.mode, "DAY_MODE_H11")
        self.assertEqual(mode.source_hour, 7)

    def test_h3_h49_then_h7_h_plus_1_25_anchors_at_h7(self):
        mode, _ = resolve_or_anchor_day_mode(None, 3, "03:49")
        mode, anchored = resolve_or_anchor_day_mode(mode, 7, "08:25")
        self.assertTrue(anchored)
        self.assertEqual(mode.mode, "DAY_MODE_H_PLUS_1_25")
        self.assertEqual(mode.source_hour, 7)

    def test_already_anchored_does_not_reanchor(self):
        existing = DayMode(mode="DAY_MODE_H11", source_hour=3, source_entry_time="03:11", source_branch="H_11")
        mode, anchored = resolve_or_anchor_day_mode(existing, 7, "08:25")
        self.assertFalse(anchored)
        self.assertEqual(mode.mode, "DAY_MODE_H11")
        self.assertEqual(mode.source_hour, 3)

    def test_all_h49_no_mode(self):
        mode = None
        for h in (3, 7, 9, 12, 14):
            mode, anchored = resolve_or_anchor_day_mode(mode, h, f"{h:02d}:49")
            self.assertFalse(anchored)
        self.assertIsNone(mode)


if __name__ == "__main__":
    unittest.main()
