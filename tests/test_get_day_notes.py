# -*- coding: utf-8 -*-
"""Unit tests for the current XAU-only daily rule notes."""
from datetime import date, datetime
import unittest

from oak_trading_reminders import _friday_of_same_week, get_day_notes


class TestGetDayNotes(unittest.TestCase):
    def test_weekday_notes_are_xau_only(self):
        for day in (
            date(2025, 4, 28),
            date(2025, 4, 29),
            date(2025, 4, 30),
            date(2025, 5, 1),
            date(2025, 5, 2),
        ):
            with self.subTest(day=day):
                blob = " ".join(get_day_notes(day, lang="VN"))
                self.assertIn("Slots:", blob)
                self.assertIn("H=2,4-6,9,12-15", blob)
                if day.weekday() != 2:
                    self.assertIn("GBPAUD", blob)
                self.assertIn("GBP", blob)

    def test_active_slots_exclude_disabled_hours(self):
        notes = " ".join(get_day_notes(date(2026, 7, 13), lang="EN"))
        self.assertIn("H=2,4-6,9,12-15", notes)
        self.assertNotIn("H=3:", notes)
        self.assertNotIn("H=10:", notes)

    def test_accepts_datetime_without_calendar_detail(self):
        notes = get_day_notes(datetime(2025, 5, 1, 10, 0, 0), lang="VN")
        self.assertNotIn("ngày 30", " ".join(notes))

    def test_weekend_has_no_schedule(self):
        self.assertIn("Cuối tuần", " ".join(get_day_notes(date(2025, 5, 3), lang="VN")))

    def test_friday_helper(self):
        self.assertEqual(_friday_of_same_week(date(2025, 7, 3)).day, 4)


if __name__ == "__main__":
    unittest.main()
