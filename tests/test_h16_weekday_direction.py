"""H16 weekday-specific KEEP_D/REVERSE_D rules (v80)."""

import unittest
from datetime import date

from mt5_signal_bot import resolve_h16_d_action, friday_d_action


class FridayDActionTests(unittest.TestCase):
    def test_first_friday_day_3_keep(self):
        # First Friday, day=3 → KEEP_D
        self.assertEqual(friday_d_action(date(2026, 7, 3)), "KEEP_D")

    def test_first_friday_day_4_keep(self):
        # First Friday, day=4 → KEEP_D
        self.assertEqual(friday_d_action(date(2026, 4, 3)), "KEEP_D")

    def test_first_friday_day_7_keep(self):
        # First Friday, day=7 → KEEP_D (Nov 7 2025 is first Friday)
        self.assertEqual(friday_d_action(date(2025, 11, 7)), "KEEP_D")

    def test_first_friday_day_5_reverse(self):
        # First Friday, day=5 → REVERSE_D (not in {3,4,7})
        self.assertEqual(friday_d_action(date(2026, 6, 5)), "REVERSE_D")

    def test_second_friday_reverse(self):
        # Second Friday → REVERSE_D
        self.assertEqual(friday_d_action(date(2026, 7, 10)), "REVERSE_D")

    def test_third_friday_keep(self):
        # Third Friday → KEEP_D
        self.assertEqual(friday_d_action(date(2026, 7, 17)), "KEEP_D")

    def test_fourth_friday_keep(self):
        # Fourth Friday → KEEP_D
        self.assertEqual(friday_d_action(date(2026, 7, 24)), "KEEP_D")

    def test_fifth_friday_keep(self):
        # Fifth Friday → KEEP_D
        self.assertEqual(friday_d_action(date(2026, 7, 31)), "KEEP_D")


class ResolveH16DActionTests(unittest.TestCase):
    def test_monday_uses_previous_friday(self):
        # Monday 2026-07-27 → previous Friday 2026-07-24 (4th Friday → KEEP_D)
        self.assertEqual(resolve_h16_d_action(date(2026, 7, 27)), "KEEP_D")

    def test_tuesday_reverse(self):
        # Tuesday → REVERSE_D
        self.assertEqual(resolve_h16_d_action(date(2026, 7, 28)), "REVERSE_D")

    def test_wednesday_reverse(self):
        # Wednesday → REVERSE_D
        self.assertEqual(resolve_h16_d_action(date(2026, 7, 29)), "REVERSE_D")

    def test_thursday_keep(self):
        # Thursday → KEEP_D (prev Wednesday not 30th or 1st)
        self.assertEqual(resolve_h16_d_action(date(2026, 7, 30)), "KEEP_D")

    def test_thursday_prev_wed_30th_reverse(self):
        # Thursday when previous Wednesday is 30th → REVERSE_D
        # e.g., Thursday 2026-07-01 → prev Wed = June 30
        self.assertEqual(resolve_h16_d_action(date(2026, 7, 1)), "REVERSE_D")

    def test_thursday_prev_wed_1st_reverse(self):
        # Thursday when previous Wednesday is 1st → REVERSE_D
        # e.g., Thursday 2026-04-02 → prev Wed = April 1
        self.assertEqual(resolve_h16_d_action(date(2026, 4, 2)), "REVERSE_D")

    def test_friday_uses_own_rule(self):
        # Friday 2026-07-31 → 5th Friday → KEEP_D
        self.assertEqual(resolve_h16_d_action(date(2026, 7, 31)), "KEEP_D")


if __name__ == "__main__":
    unittest.main()
