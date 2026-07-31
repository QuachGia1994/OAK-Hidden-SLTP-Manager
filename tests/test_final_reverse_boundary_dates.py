import unittest
from datetime import date
from mt5_signal_bot import should_reverse_final_signal

class TestFinalReverseBoundaryDates(unittest.TestCase):
    def test_wednesday_day_30_boundary(self):
        # 2026-09-30 is Wednesday
        wed = date(2026, 9, 30)
        self.assertEqual(wed.weekday(), 2)

        # Thursday 2026-10-01
        thu = date(2026, 10, 1)
        self.assertEqual(thu.weekday(), 3)

        # H3 Thursday after Wed day 30: KEEP
        rev_h3, reason_h3 = should_reverse_final_signal(3, thu)
        self.assertFalse(rev_h3)
        self.assertEqual(reason_h3, "H3_THURSDAY_PREVIOUS_WED_MONTH_BOUNDARY_EXCEPTION")

        # H16 Thursday after Wed day 30: REVERSE
        rev_h16, reason_h16 = should_reverse_final_signal(16, thu)
        self.assertTrue(rev_h16)
        self.assertEqual(reason_h16, "H16_THURSDAY_PREVIOUS_WED_MONTH_BOUNDARY")

    def test_wednesday_day_1_boundary(self):
        # 2026-07-01 is Wednesday
        wed = date(2026, 7, 1)
        self.assertEqual(wed.weekday(), 2)

        # Thursday 2026-07-02
        thu = date(2026, 7, 2)
        self.assertEqual(thu.weekday(), 3)

        # H3 Thursday after Wed day 1: KEEP
        rev_h3, reason_h3 = should_reverse_final_signal(3, thu)
        self.assertFalse(rev_h3)
        self.assertEqual(reason_h3, "H3_THURSDAY_PREVIOUS_WED_MONTH_BOUNDARY_EXCEPTION")

        # H16 Thursday after Wed day 1: REVERSE
        rev_h16, reason_h16 = should_reverse_final_signal(16, thu)
        self.assertTrue(rev_h16)
        self.assertEqual(reason_h16, "H16_THURSDAY_PREVIOUS_WED_MONTH_BOUNDARY")

if __name__ == "__main__":
    unittest.main()
