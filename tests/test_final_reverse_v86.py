import unittest
from datetime import date
from mt5_signal_bot import should_reverse_final_signal, apply_special_adjustment, reverse_signal

class TestFinalReverseV86(unittest.TestCase):
    def test_h3_wednesday_reverses(self):
        # 2026-07-29 is Wednesday (weekday=2)
        d = date(2026, 7, 29)
        rev, reason = should_reverse_final_signal(3, d)
        self.assertTrue(rev)
        self.assertEqual(reason, "H3_WEDNESDAY")

    def test_h3_thursday_normal_reverses(self):
        # 2026-07-23 is Thursday (weekday=3). Yesterday 2026-07-22 (Wednesday) was day 22.
        d = date(2026, 7, 23)
        rev, reason = should_reverse_final_signal(3, d)
        self.assertTrue(rev)
        self.assertEqual(reason, "H3_THURSDAY")

    def test_h3_thursday_prev_wed_boundary_day30_keeps(self):
        # 2026-10-01 is Thursday. Yesterday 2026-09-30 was Wednesday day 30.
        d = date(2026, 10, 1)
        rev, reason = should_reverse_final_signal(3, d)
        self.assertFalse(rev)
        self.assertEqual(reason, "H3_THURSDAY_PREVIOUS_WED_MONTH_BOUNDARY_EXCEPTION")

    def test_h3_thursday_prev_wed_boundary_day1_keeps(self):
        # 2026-07-02 is Thursday. Yesterday 2026-07-01 was Wednesday day 1.
        d = date(2026, 7, 2)
        rev, reason = should_reverse_final_signal(3, d)
        self.assertFalse(rev)
        self.assertEqual(reason, "H3_THURSDAY_PREVIOUS_WED_MONTH_BOUNDARY_EXCEPTION")

    def test_h3_friday_special_days_reverse(self):
        # Friday day 3: 2026-07-03
        rev3, r3 = should_reverse_final_signal(3, date(2026, 7, 3))
        self.assertTrue(rev3)
        self.assertEqual(r3, "H3_FRIDAY_SPECIAL_DAY_3_4_7")

        # Friday day 4: 2026-09-04
        rev4, r4 = should_reverse_final_signal(3, date(2026, 9, 4))
        self.assertTrue(rev4)
        self.assertEqual(r4, "H3_FRIDAY_SPECIAL_DAY_3_4_7")

        # Friday day 7: 2026-08-07
        rev7, r7 = should_reverse_final_signal(3, date(2026, 8, 7))
        self.assertTrue(rev7)
        self.assertEqual(r7, "H3_FRIDAY_SPECIAL_DAY_3_4_7")

    def test_h3_friday_other_keeps(self):
        # Friday day 10: 2026-07-10
        rev, r = should_reverse_final_signal(3, date(2026, 7, 10))
        self.assertFalse(rev)

    def test_h14_tuesday_and_wednesday_reverse(self):
        # Tuesday: 2026-07-28
        rev_tue, r_tue = should_reverse_final_signal(14, date(2026, 7, 28))
        self.assertTrue(rev_tue)
        self.assertEqual(r_tue, "H14_TUESDAY")

        # Wednesday: 2026-07-29
        rev_wed, r_wed = should_reverse_final_signal(14, date(2026, 7, 29))
        self.assertTrue(rev_wed)
        self.assertEqual(r_wed, "H14_WEDNESDAY")

        # Thursday: 2026-07-30 -> KEEP
        rev_thu, r_thu = should_reverse_final_signal(14, date(2026, 7, 30))
        self.assertFalse(rev_thu)

    def test_h16_tuesday_and_wednesday_reverse(self):
        # Tuesday: 2026-07-28
        rev_tue, r_tue = should_reverse_final_signal(16, date(2026, 7, 28))
        self.assertTrue(rev_tue)

        # Wednesday: 2026-07-29
        rev_wed, r_wed = should_reverse_final_signal(16, date(2026, 7, 29))
        self.assertTrue(rev_wed)

    def test_h16_thursday_normal_keeps(self):
        # 2026-07-23 is Thursday (yesterday Wed 22) -> KEEP
        rev, r = should_reverse_final_signal(16, date(2026, 7, 23))
        self.assertFalse(rev)

    def test_h16_thursday_prev_wed_boundary_reverses(self):
        # 2026-10-01 (Thu) (yesterday Wed 30) -> REVERSE
        rev, r = should_reverse_final_signal(16, date(2026, 10, 1))
        self.assertTrue(rev)
        self.assertEqual(r, "H16_THURSDAY_PREVIOUS_WED_MONTH_BOUNDARY")

    def test_h16_friday_special_days_keeps(self):
        # Friday day 3: 2026-07-03 -> KEEP
        rev, r = should_reverse_final_signal(16, date(2026, 7, 3))
        self.assertFalse(rev)
        self.assertEqual(r, "H16_FRIDAY_SPECIAL_DAY_3_4_7_EXCEPTION")

    def test_h16_friday_other_reverses(self):
        # Friday day 10: 2026-07-10 -> REVERSE
        rev, r = should_reverse_final_signal(16, date(2026, 7, 10))
        self.assertTrue(rev)
        self.assertEqual(r, "H16_FRIDAY_NORMAL")

    def test_apply_special_adjustment_direction_inversion(self):
        d = date(2026, 7, 29) # Wed
        out, reason = apply_special_adjustment("BUY", broker_date=d, slot_hour=3)
        self.assertEqual(out, "SELL")
        self.assertIsNotNone(reason)

        out_sell, _ = apply_special_adjustment("SELL", broker_date=d, slot_hour=3)
        self.assertEqual(out_sell, "BUY")

        out_wait, _ = apply_special_adjustment("WAIT", broker_date=d, slot_hour=3)
        self.assertEqual(out_wait, "WAIT")

if __name__ == "__main__":
    unittest.main()
