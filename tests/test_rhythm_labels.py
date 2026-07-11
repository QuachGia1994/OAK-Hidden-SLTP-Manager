# -*- coding: utf-8 -*-
"""Regression tests for the five trading rhythm labels."""
import unittest

from mt5_signal_bot import get_rhythm_label


class TestRhythmLabels(unittest.TestCase):
    def test_all_active_hours_map_to_a_rhythm(self):
        expected = {
            2: "Nhịp 1", 3: "Nhịp 1", 4: "Nhịp 1",
            5: "Nhịp 2", 6: "Nhịp 2", 7: "Nhịp 2", 8: "Nhịp 2",
            9: "Nhịp 3", 10: "Nhịp 3", 11: "Nhịp 3",
            12: "Nhịp 4", 13: "Nhịp 4",
            15: "Nhịp 5",
        }
        for hour, label in expected.items():
            with self.subTest(hour=hour):
                self.assertEqual(get_rhythm_label(hour), label)

    def test_disabled_hours_have_no_label(self):
        for hour in (1, 14, 16):
            with self.subTest(hour=hour):
                self.assertIsNone(get_rhythm_label(hour))


if __name__ == "__main__":
    unittest.main()
