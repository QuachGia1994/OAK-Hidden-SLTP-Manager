# -*- coding: utf-8 -*-
"""Weekday-aware target hours: T5=H5-15, else H2-15."""
import unittest
from datetime import datetime, timezone

from mt5_signal_bot import get_target_hours


class TestGetTargetHours(unittest.TestCase):
    def test_thursday_h5_to_15(self):
        # 2026-07-09 is Thursday
        dt = datetime(2026, 7, 9, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(get_target_hours(dt), list(range(5, 16)))
        self.assertEqual(get_target_hours(weekday=3), list(range(5, 16)))

    def test_mon_tue_wed_fri_h2_to_15(self):
        for wd in (0, 1, 2, 4):
            with self.subTest(wd=wd):
                hours = get_target_hours(weekday=wd)
                self.assertEqual(hours, list(range(2, 16)))
                self.assertEqual(hours[0], 2)
                self.assertEqual(hours[-1], 15)

    def test_weekend_empty(self):
        self.assertEqual(get_target_hours(weekday=5), [])
        self.assertEqual(get_target_hours(weekday=6), [])


if __name__ == "__main__":
    unittest.main()
