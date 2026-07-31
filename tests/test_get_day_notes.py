# -*- coding: utf-8 -*-
"""Unit tests for the current daily rule notes (v82)."""
from datetime import date
import unittest

from oak_trading_reminders import _friday_of_same_week, get_day_notes

class TestGetDayNotes(unittest.TestCase):
    def test_weekday_notes_v82(self):
        for day in (
            date(2025, 4, 28),
            date(2025, 4, 29),
            date(2025, 4, 30),
            date(2025, 5, 1),
            date(2025, 5, 2),
        ):
            with self.subTest(day=day):
                blob = " ".join(get_day_notes(day, lang="VN"))
                self.assertIn("Entry Engine", blob)
                self.assertIn("Signal Engine", blob)
                self.assertIn("D-Direction", blob)
                self.assertIn("M30", blob)
                self.assertIn("H4", blob)
                self.assertIn("GBPJPY và GBPCAD tạm Tắt (OFF)", blob)

    def test_weekend_has_no_schedule(self):
        self.assertIn("Cuối tuần", " ".join(get_day_notes(date(2025, 5, 3), lang="VN")))
        self.assertIn("Weekend", " ".join(get_day_notes(date(2025, 5, 4), lang="EN")))

    def test_friday_helper(self):
        self.assertEqual(_friday_of_same_week(date(2025, 7, 3)).day, 4)

if __name__ == "__main__":
    unittest.main()
