# -*- coding: utf-8 -*-
"""Unit tests for XAU-only daily rule notes."""
import unittest
from datetime import date, datetime

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
                self.assertIn("H=2-10,12-13,15,17", blob)
                self.assertIn("Chỉ XAUUSD", blob)
                self.assertNotIn("GBP", blob)
                self.assertNotIn("no-gold", blob)
                self.assertNotIn("KHÔNG ĐÁNH", blob)

    def test_friday_no_longer_reverses_xau(self):
        notes = get_day_notes(date(2026, 7, 10), lang="EN")
        blob = " ".join(notes)
        self.assertIn("XAUUSD only", blob)
        self.assertNotIn("reverse signal to gold", blob)
        self.assertNotIn("GBP", blob)

    def test_tuesday_reverses_thursday_uses_history(self):
        tue_blob = " ".join(get_day_notes(date(2026, 7, 14), lang="EN"))
        thu_blob = " ".join(get_day_notes(date(2026, 7, 16), lang="EN"))

        self.assertIn("H=2: reverses XAU by default.", tue_blob)
        self.assertIn("H=2: uses T2 H=2 signal from history.", thu_blob)

    def test_accepts_datetime_without_special_detail(self):
        notes = get_day_notes(datetime(2025, 5, 1, 10, 0, 0), lang="VN")
        blob = " ".join(notes)
        self.assertIn("Chỉ XAUUSD", blob)
        self.assertNotIn("ngày 30", blob)

    def test_weekend_has_no_schedule(self):
        self.assertIn("Cuối tuần", " ".join(get_day_notes(date(2025, 5, 3), lang="VN")))

    def test_friday_helper(self):
        thu = date(2025, 7, 3)
        self.assertEqual(_friday_of_same_week(thu).day, 4)


if __name__ == "__main__":
    unittest.main()
