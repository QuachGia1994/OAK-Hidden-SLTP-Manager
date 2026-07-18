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
                self.assertIn("Chỉ XAUUSD", blob)
                self.assertNotIn("GBP", blob)
                self.assertNotIn("no-gold", blob)

    def test_active_slots_exclude_disabled_hours(self):
        notes = " ".join(get_day_notes(date(2026, 7, 13), lang="EN"))
        self.assertIn("H=2-5,7-9,12-13,15", notes)
        self.assertNotIn("H=10", notes)
        self.assertNotIn("H=11", notes)
        self.assertNotIn("H=14", notes)

    def test_thursday_uses_monday_h2_history(self):
        notes = " ".join(get_day_notes(date(2026, 7, 16), lang="EN"))
        self.assertIn("H=2: reuses Monday H=2; special weeks reverse it.", notes)

    def test_friday_h2_has_no_special_calendar_rule(self):
        notes = " ".join(get_day_notes(date(2026, 7, 10), lang="EN"))
        self.assertIn("H=2: M5/M30 with XAUUSD M30 post-processing.", notes)
        self.assertNotIn("special weeks", notes)
        self.assertNotIn("GBP", notes)

    def test_all_weekdays_explain_h3_and_h7(self):
        for weekday in range(5):
            day = date(2026, 7, 13 + weekday)
            with self.subTest(day=day):
                self.assertIn(
                    "H=3 and H=7: reverse the final H=2 direction.",
                    " ".join(get_day_notes(day, lang="EN")),
                )

    def test_accepts_datetime_without_calendar_detail(self):
        notes = get_day_notes(datetime(2025, 5, 1, 10, 0, 0), lang="VN")
        self.assertNotIn("ngày 30", " ".join(notes))

    def test_weekend_has_no_schedule(self):
        self.assertIn("Cuối tuần", " ".join(get_day_notes(date(2025, 5, 3), lang="VN")))

    def test_friday_helper(self):
        self.assertEqual(_friday_of_same_week(date(2025, 7, 3)).day, 4)


if __name__ == "__main__":
    unittest.main()
