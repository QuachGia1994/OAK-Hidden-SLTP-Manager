# -*- coding: utf-8 -*-
"""Weekday-aware target hours with disabled H=11/H=14 slots."""
import unittest
from datetime import datetime, timezone

from mt5_signal_bot import get_target_hours


class TestGetTargetHours(unittest.TestCase):
    def test_all_weekdays_include_h2_h17_and_exclude_h11_h14(self):
        for wd in (0, 1, 2, 3, 4):
            with self.subTest(wd=wd):
                hours = get_target_hours(weekday=wd)
                self.assertEqual(hours, [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 13, 15, 17])
                self.assertEqual(hours[0], 2)
                self.assertEqual(hours[-1], 17)
                self.assertNotIn(11, hours)
                self.assertNotIn(14, hours)
                self.assertIn(17, hours)

    def test_thursday_includes_early_and_late(self):
        dt = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)
        hours = get_target_hours(dt)
        self.assertIn(3, hours)
        self.assertIn(4, hours)
        self.assertIn(12, hours)
        self.assertNotIn(11, hours)
        self.assertNotIn(14, hours)
        self.assertIn(15, hours)
        self.assertIn(17, hours)

    def test_weekend_empty(self):
        self.assertEqual(get_target_hours(weekday=5), [])
        self.assertEqual(get_target_hours(weekday=6), [])


if __name__ == "__main__":
    unittest.main()
