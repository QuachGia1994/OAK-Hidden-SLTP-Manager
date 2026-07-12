# -*- coding: utf-8 -*-
"""Unit tests for Thursday-only special day notes in get_day_notes()."""
import unittest
from datetime import date, datetime, timedelta

from oak_trading_reminders import get_day_notes, _friday_of_same_week


class TestGetDayNotesThursdayOnly(unittest.TestCase):
    def test_thursday_after_wednesday_day_30(self):
        # 2025-05-01 is Thursday; yesterday Wed 2025-04-30
        notes = get_day_notes(date(2025, 5, 1), lang="VN")
        self.assertTrue(any("Thứ 4 hôm qua ngày 30" in n for n in notes), notes)

    def test_thursday_after_wednesday_day_1(self):
        # Find a Thursday whose yesterday Wed is day 1
        # 2025-10-02 is Thursday; Wed=2025-10-01
        notes = get_day_notes(date(2025, 10, 2), lang="VN")
        self.assertTrue(any("Thứ 4 hôm qua ngày 1" in n for n in notes), notes)

    def test_thursday_with_friday_day_3(self):
        # Thursday before Friday day 3: 2025-01-02 is Thursday, Fri=3
        notes = get_day_notes(date(2025, 1, 2), lang="VN")
        self.assertTrue(any("Thứ 6 ngày 3" in n for n in notes), notes)

    def test_thursday_with_friday_day_4(self):
        # 2025-07-03 is Thursday, Fri=4
        notes = get_day_notes(date(2025, 7, 3), lang="VN")
        self.assertTrue(any("Thứ 6 ngày 4" in n for n in notes), notes)

    def test_thursday_with_friday_day_7(self):
        # 2025-02-06 is Thursday, Fri=7
        notes = get_day_notes(date(2025, 2, 6), lang="VN")
        self.assertTrue(any("Thứ 6 ngày 7" in n for n in notes), notes)

    def test_wednesday_has_core_schedule(self):
        notes = get_day_notes(date(2025, 4, 30), lang="VN")
        blob = " ".join(notes)
        self.assertIn("H=2-15", blob)
        self.assertIn("H=3-4", blob)
        self.assertFalse(any("tính lại W1" in n for n in notes))

    def test_monday_has_core_schedule(self):
        notes = get_day_notes(date(2025, 4, 28), lang="VN")
        blob = " ".join(notes)
        self.assertIn("H=2-15", blob)

    def test_friday_en_matches_bot(self):
        notes = get_day_notes(date(2026, 7, 10), lang="EN")
        blob = " ".join(notes)
        self.assertIn("H=2-15", blob)
        self.assertIn("H=3-4", blob)
        self.assertIn("H=3-11", blob)  # Fri no-gold band
        self.assertIn("H=12,13,15", blob)  # Fri gold only
        self.assertNotIn("trade normally per schedule", blob)

    def test_normal_thursday_default(self):
        notes = get_day_notes(date(2026, 7, 9), lang="VN")
        blob = " ".join(notes)
        self.assertIn("H=2-15", blob)
        self.assertIn("H=3-4", blob)

    def test_accepts_datetime(self):
        notes = get_day_notes(datetime(2025, 5, 1, 10, 0, 0), lang="VN")
        self.assertTrue(any("ngày 30" in n for n in notes))

    def test_friday_helper(self):
        thu = date(2025, 7, 3)
        self.assertEqual(_friday_of_same_week(thu).day, 4)


if __name__ == "__main__":
    unittest.main()
