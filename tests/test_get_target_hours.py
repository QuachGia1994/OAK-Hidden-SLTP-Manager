# -*- coding: utf-8 -*-
"""Weekday-aware target hours, including Monday's special H=2 slot."""
import unittest
from datetime import datetime, timezone

from mt5_signal_bot import get_target_hours


class TestGetTargetHours(unittest.TestCase):
    def test_monday_includes_special_h2_but_other_weekdays_exclude_it(self):
        self.assertEqual(
            get_target_hours(weekday=0),
            [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15],
        )
        for wd in (1, 2, 3, 4):
            with self.subTest(wd=wd):
                hours = get_target_hours(weekday=wd)
                self.assertEqual(hours, [3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15])
                self.assertEqual(hours[0], 3)
                self.assertEqual(hours[-1], 15)
                self.assertNotIn(2, hours)
                self.assertNotIn(14, hours)

    def test_thursday_includes_early_and_late(self):
        dt = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)  # Thursday
        hours = get_target_hours(dt)
        self.assertIn(3, hours)
        self.assertIn(4, hours)
        self.assertIn(12, hours)
        self.assertIn(15, hours)

    def test_weekend_empty(self):
        self.assertEqual(get_target_hours(weekday=5), [])
        self.assertEqual(get_target_hours(weekday=6), [])


if __name__ == "__main__":
    unittest.main()
