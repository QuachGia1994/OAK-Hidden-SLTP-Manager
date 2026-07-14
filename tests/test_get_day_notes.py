# -*- coding: utf-8 -*-
"""Unit tests for daily rule notes synced with the dashboard matrix."""
import unittest
from datetime import date, datetime

from oak_trading_reminders import get_day_notes, _friday_of_same_week


class TestGetDayNotes(unittest.TestCase):
    def test_special_calendar_details_are_not_announced(self):
        cases = (
            date(2025, 5, 1),   # Thu after Wed day 30
            date(2025, 10, 2),  # Thu after Wed day 1
            date(2025, 1, 2),   # Thu before Fri day 3
            date(2025, 7, 3),   # Thu before Fri day 4
            date(2025, 2, 6),   # Thu before Fri day 7
        )
        blocked = ("ngày 30", "ngày 1", "ngày 3", "ngày 4", "ngày 7", "tính lại W1", "recalculate W1")
        for day in cases:
            with self.subTest(day=day):
                blob = " ".join(get_day_notes(day, lang="VN"))
                self.assertFalse(any(term in blob for term in blocked), blob)

    def test_h2_notes_match_weekday_matrix(self):
        cases = (
            (date(2025, 4, 29), "H=2: đảo signal mặc định · Focus GBPAUD/GBPJPY ngược XAU"),
            (date(2025, 4, 30), "H=2: bình thường · Focus GBPAUD/GBPJPY ngược XAU"),
            (date(2025, 5, 1), "H=2: đảo mặc định; gặp calendar exception thì XAU bình thường"),
            (date(2025, 1, 3), "H=2: mặc định XAU bình thường; ngày đặc biệt thì đảo signal ra Vàng"),
        )
        for day, expected in cases:
            with self.subTest(day=day):
                blob = " ".join(get_day_notes(day, lang="VN"))
                self.assertIn(expected, blob)

    def test_wednesday_has_core_schedule(self):
        notes = get_day_notes(date(2025, 4, 30), lang="VN")
        blob = " ".join(notes)
        self.assertIn("H=2-10,12-13,15,17", blob)
        self.assertIn("H=3-4", blob)
        self.assertFalse(any("tính lại W1" in n for n in notes))

    def test_monday_has_core_schedule(self):
        notes = get_day_notes(date(2025, 4, 28), lang="VN")
        blob = " ".join(notes)
        self.assertIn("H=2-10,12-13,15,17", blob)
        self.assertIn("H=3-10,12-13,15", blob)

    def test_friday_en_matches_bot(self):
        notes = get_day_notes(date(2026, 7, 10), lang="EN")
        blob = " ".join(notes)
        self.assertIn("H=2-10,12-13,15,17", blob)
        self.assertIn("H=2: normal by default; special calendar reverses signal to gold", blob)
        self.assertIn("H=3-7 and H=9-10", blob)
        self.assertIn("reverse signal to gold", blob)
        self.assertNotIn("trade normally per schedule", blob)

    def test_normal_thursday_default(self):
        notes = get_day_notes(date(2026, 7, 9), lang="VN")
        blob = " ".join(notes)
        self.assertIn("H=2-10,12-13,15,17", blob)
        self.assertIn("H=3-4", blob)

    def test_accepts_datetime_without_special_detail(self):
        notes = get_day_notes(datetime(2025, 5, 1, 10, 0, 0), lang="VN")
        blob = " ".join(notes)
        self.assertIn("H=2: đảo mặc định; gặp calendar exception thì XAU bình thường", blob)
        self.assertNotIn("ngày 30", blob)

    def test_friday_helper(self):
        thu = date(2025, 7, 3)
        self.assertEqual(_friday_of_same_week(thu).day, 4)


if __name__ == "__main__":
    unittest.main()
