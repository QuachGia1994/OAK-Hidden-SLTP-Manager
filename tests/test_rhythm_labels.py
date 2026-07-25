# -*- coding: utf-8 -*-
"""Regression tests for the active trading rhythm labels."""
import unittest

from mt5_signal_bot import get_rhythm_label


class TestRhythmLabels(unittest.TestCase):
    def test_all_active_hours_map_to_a_rhythm(self):
        expected = {
            2: "Nhịp 0 · XAU",
            4: "Nhịp 1 · JPY",
            5: "Nhịp 2 · AUD",
            6: "Nhịp 2 · AUD",
            8: "Nhịp 2 · AUD",
            9: "Nhịp 3 · GBP",
            12: "Nhịp 4 · EUR",
            13: "Nhịp 4 · EUR",
            14: "Nhịp 5 · USD",
            15: "Nhịp 5 · USD",
        }
        for hour, label in expected.items():
            with self.subTest(hour=hour):
                self.assertEqual(get_rhythm_label(hour), label)

    def test_disabled_hours_have_no_label(self):
        for hour in (1, 3, 10, 11, 16, 17):
            with self.subTest(hour=hour):
                self.assertIsNone(get_rhythm_label(hour))


if __name__ == "__main__":
    unittest.main()
