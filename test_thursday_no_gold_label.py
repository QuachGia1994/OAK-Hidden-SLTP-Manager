# -*- coding: utf-8 -*-
"""Regression tests for the current Thursday and Friday schedule rules."""
import unittest
from datetime import datetime

from mt5_signal_bot import is_thursday_no_gold_slot
from oak_trading_reminders import get_day_notes


class TestThursdaySchedule(unittest.TestCase):
    def test_thursday_h12_plus_has_no_no_gold_label(self):
        thursday = datetime(2026, 7, 9, 13, 0)
        for hour in (12, 13, 14, 15):
            self.assertFalse(is_thursday_no_gold_slot(hour, thursday))

    def test_thursday_notes_do_not_mark_h12_plus_no_gold(self):
        notes = get_day_notes(datetime(2026, 7, 9), lang="VN")
        self.assertFalse(any("H≥12" in note for note in notes))


if __name__ == "__main__":
    unittest.main()
