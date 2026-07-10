# -*- coding: utf-8 -*-
"""Weekday-aware target hours: Mon–Fri H=3-13,15 (no H=14)."""
import unittest
from datetime import datetime, timezone

from mt5_signal_bot import get_target_hours, TARGET_HOURS


class TestGetTargetHours(unittest.TestCase):
    def test_all_weekdays_no_h14(self):
        expected = [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15]
        self.assertEqual(TARGET_HOURS, expected)
        for wd in (0, 1, 2, 3, 4):  # Mon–Fri
            with self.subTest(wd=wd):
                hours = get_target_hours(weekday=wd)
                self.assertEqual(hours, expected)
                self.assertNotIn(14, hours)
                self.assertEqual(hours[0], 3)
                self.assertEqual(hours[-1], 15)

    def test_thursday_includes_early_and_late(self):
        dt = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)  # Thursday
        hours = get_target_hours(dt)
        self.assertIn(3, hours)
        self.assertIn(4, hours)
        self.assertIn(12, hours)
        self.assertIn(15, hours)
        self.assertNotIn(14, hours)

    def test_weekend_empty(self):
        self.assertEqual(get_target_hours(weekday=5), [])
        self.assertEqual(get_target_hours(weekday=6), [])


if __name__ == "__main__":
    unittest.main()
