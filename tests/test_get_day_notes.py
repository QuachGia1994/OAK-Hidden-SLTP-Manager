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
                self.assertIn("H=3,4,6,9,12,14,16", blob)
                self.assertIn("XAUUSD", blob)

    def test_active_slots_exclude_disabled_hours(self):
        notes = " ".join(get_day_notes(date(2026, 7, 13), lang="EN"))
        self.assertIn("H=3,4,6,9,12,14,16", notes)
        self.assertNotIn("H=2:", notes)
        self.assertNotIn("H=10:", notes)
        self.assertNotIn("H=15", notes)

    def test_notes_publish_the_new_broker_schedule(self):
        notes = " ".join(get_day_notes(date(2026, 7, 14), lang="EN"))
        for publication in ("H3 03:00", "H4 04:00", "H6 06:00", "H16 16:00"):
            with self.subTest(publication=publication):
                self.assertIn(publication, notes)

    def test_notes_describe_yesterday_h1_and_today_m15_entry_rule(self):
        notes = " ".join(get_day_notes(date(2026, 7, 14), lang="EN"))

        self.assertIn("yesterday H8/H7", notes)
        self.assertIn("Matching GBPUSD/GBPAUD results", notes)
        self.assertIn("H9 skips 08:45 and uses 08:30/08:15/08:00", notes)
        self.assertIn("H3 SW → 04:49, BT → 03:49", notes)
        self.assertNotIn("M30", notes)

    def test_special_pair_notes_keep_late_slots(self):
        for day in (date(2026, 8, 6), date(2026, 8, 7)):
            with self.subTest(day=day):
                notes = " ".join(get_day_notes(day, lang="EN"))
                self.assertIn("H=3,4,6,9,12,14,16", notes)
                self.assertNotIn("are not generated", notes)
                self.assertNotIn("are suppressed", notes)

    def test_new_year_pair_is_not_special(self):
        for day in (date(2026, 12, 31), date(2027, 1, 1)):
            with self.subTest(day=day):
                notes = " ".join(get_day_notes(day, lang="EN"))
                self.assertNotIn("are not generated", notes)

    def test_accepts_datetime_without_calendar_detail(self):
        notes = get_day_notes(datetime(2025, 5, 1, 10, 0, 0), lang="VN")
        self.assertNotIn("ngày 30", " ".join(notes))

    def test_weekend_has_no_schedule(self):
        self.assertIn("Cuối tuần", " ".join(get_day_notes(date(2025, 5, 3), lang="VN")))

    def test_friday_helper(self):
        self.assertEqual(_friday_of_same_week(date(2025, 7, 3)).day, 4)


if __name__ == "__main__":
    unittest.main()
