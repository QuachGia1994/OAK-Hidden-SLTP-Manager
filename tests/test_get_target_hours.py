# -*- coding: utf-8 -*-
"""Weekday-aware active logical signal slots."""
import unittest
from datetime import datetime, timezone

from mt5_signal_bot import get_target_hours


class TestGetTargetHours(unittest.TestCase):
    def test_all_weekdays_use_only_the_active_logical_slots(self):
        for wd in (0, 1, 2, 3, 4):
            with self.subTest(wd=wd):
                hours = get_target_hours(weekday=wd)
                self.assertEqual(hours, [3, 4, 5, 6, 9, 12, 14, 16])
                self.assertEqual(hours[0], 3)
                self.assertEqual(hours[-1], 16)
                self.assertNotIn(2, hours)
                self.assertNotIn(10, hours)
                self.assertNotIn(11, hours)
                self.assertNotIn(13, hours)
                self.assertNotIn(15, hours)
                self.assertNotIn(1500, hours)

    def test_thursday_includes_early_and_late(self):
        dt = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)
        hours = get_target_hours(dt)
        self.assertIn(3, hours)
        self.assertIn(4, hours)
        self.assertIn(6, hours)
        self.assertIn(9, hours)
        self.assertIn(12, hours)
        self.assertIn(14, hours)
        self.assertNotIn(1500, hours)
        self.assertIn(16, hours)
        self.assertNotIn(10, hours)

    def test_weekend_empty(self):
        self.assertEqual(get_target_hours(weekday=5), [])
        self.assertEqual(get_target_hours(weekday=6), [])


if __name__ == "__main__":
    unittest.main()
