# -*- coding: utf-8 -*-
"""Unit tests for the current daily rule notes."""
from datetime import date, datetime
import unittest

from oak_trading_reminders import _friday_of_same_week, get_day_notes

class TestGetDayNotes(unittest.TestCase):
    def test_weekday_notes_v71(self):
        for day in (
            date(2025, 4, 28),
            date(2025, 4, 29),
            date(2025, 4, 30),
            date(2025, 5, 1),
            date(2025, 5, 2),
        ):
            with self.subTest(day=day):
                blob = " ".join(get_day_notes(day, lang="VN"))
                self.assertIn("XAUUSD, GBPUSD, GBPAUD, GBPJPY và GBPCAD", blob)
                self.assertIn("GBPAUD M15 H−00:15", blob)
                self.assertIn("GBPAUD M15 mở H:30, đóng H:45", blob)
                self.assertIn("04:00/03:00/02:00", blob)
                self.assertIn("10 rule", blob)
                self.assertIn("15:25 và 16:49", blob)

    def test_weekend_has_no_schedule(self):
        self.assertIn("Cuối tuần", " ".join(get_day_notes(date(2025, 5, 3), lang="VN")))
        self.assertIn("Weekend", " ".join(get_day_notes(date(2025, 5, 4), lang="EN")))

    def test_friday_helper(self):
        self.assertEqual(_friday_of_same_week(date(2025, 7, 3)).day, 4)

if __name__ == "__main__":
    unittest.main()
