"""Test v84 Final Inversion Rules (Matrix & Pure Helper)."""
import unittest
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mt5_signal_bot import apply_special_adjustment


class TestV84FinalInversions(unittest.TestCase):
    """Verify exact v84 final inversion matrix for H3, H14, and H16 across weekdays."""

    # Python weekdays: Mon=0, Tue=1, Wed=2, Thu=3, Fri=4
    # Dates:
    # Mon 2026-07-27 (0)
    # Tue 2026-07-28 (1)
    # Wed 2026-07-29 (2)
    # Thu 2026-07-30 (3)
    # Fri 2026-07-31 (4)

    def test_h3_wednesday_source_d_inverts(self):
        broker_date = datetime(2026, 7, 29).date() # Wed
        sig, rule = apply_special_adjustment("BUY", broker_date=broker_date, slot_hour=3, primary_source="D_DIRECTION")
        self.assertEqual(sig, "SELL")
        self.assertEqual(rule, "H3_WEDNESDAY")

    def test_h3_thursday_source_d_inverts(self):
        broker_date = datetime(2026, 7, 30).date() # Thu
        sig, rule = apply_special_adjustment("SELL", broker_date=broker_date, slot_hour=3, primary_source="D_DIRECTION")
        self.assertEqual(sig, "BUY")
        self.assertEqual(rule, "H3_THURSDAY")

    def test_h3_wednesday_source_h1_inverts_in_v86(self):
        broker_date = datetime(2026, 7, 29).date() # Wed
        sig, rule = apply_special_adjustment("BUY", broker_date=broker_date, slot_hour=3, primary_source="PREVIOUS_COMPLETED_H1")
        self.assertEqual(sig, "SELL")
        self.assertEqual(rule, "H3_WEDNESDAY")

    def test_h14_tuesday_always_inverts(self):
        broker_date = datetime(2026, 7, 28).date() # Tue
        sig_d, rule_d = apply_special_adjustment("BUY", broker_date=broker_date, slot_hour=14, primary_source="D_DIRECTION")
        self.assertEqual(sig_d, "SELL")
        self.assertEqual(rule_d, "H14_TUESDAY")

        sig_h1, rule_h1 = apply_special_adjustment("SELL", broker_date=broker_date, slot_hour=14, primary_source="PREVIOUS_COMPLETED_H1")
        self.assertEqual(sig_h1, "BUY")
        self.assertEqual(rule_h1, "H14_TUESDAY")

    def test_h14_wednesday_always_inverts(self):
        broker_date = datetime(2026, 7, 29).date() # Wed
        sig, rule = apply_special_adjustment("BUY", broker_date=broker_date, slot_hour=14, primary_source="D_DIRECTION")
        self.assertEqual(sig, "SELL")
        self.assertEqual(rule, "H14_WEDNESDAY")

    def test_h14_thursday_friday_no_inversion(self):
        thu_date = datetime(2026, 7, 30).date()
        fri_date = datetime(2026, 7, 31).date()
        sig_thu, rule_thu = apply_special_adjustment("BUY", broker_date=thu_date, slot_hour=14, primary_source="D_DIRECTION")
        sig_fri, rule_fri = apply_special_adjustment("BUY", broker_date=fri_date, slot_hour=14, primary_source="D_DIRECTION")
        self.assertEqual(sig_thu, "BUY")
        self.assertIsNone(rule_thu)
        self.assertEqual(sig_fri, "BUY")
        self.assertIsNone(rule_fri)

    def test_h16_tuesday_wednesday_friday_source_d_inverts(self):
        tue = datetime(2026, 7, 28).date()
        wed = datetime(2026, 7, 29).date()
        fri = datetime(2026, 7, 31).date()

        sig_tue, r_tue = apply_special_adjustment("BUY", broker_date=tue, slot_hour=16, primary_source="D_DIRECTION")
        self.assertEqual(sig_tue, "SELL")
        self.assertEqual(r_tue, "H16_TUESDAY")

        sig_wed, r_wed = apply_special_adjustment("SELL", broker_date=wed, slot_hour=16, primary_source="D_DIRECTION")
        self.assertEqual(sig_wed, "BUY")
        self.assertEqual(r_wed, "H16_WEDNESDAY")

        sig_fri, r_fri = apply_special_adjustment("BUY", broker_date=fri, slot_hour=16, primary_source="D_DIRECTION")
        self.assertEqual(sig_fri, "SELL")
        self.assertEqual(r_fri, "H16_FRIDAY_NORMAL")

    def test_h16_tuesday_source_h1_inverts_in_v86(self):
        tue = datetime(2026, 7, 28).date()
        sig, rule = apply_special_adjustment("BUY", broker_date=tue, slot_hour=16, primary_source="PREVIOUS_COMPLETED_H1")
        self.assertEqual(sig, "SELL")
        self.assertEqual(rule, "H16_TUESDAY")

    def test_h16_monday_thursday_no_inversion(self):
        mon = datetime(2026, 7, 27).date()
        thu = datetime(2026, 7, 30).date()

        sig_mon, r_mon = apply_special_adjustment("BUY", broker_date=mon, slot_hour=16, primary_source="D_DIRECTION")
        sig_thu, r_thu = apply_special_adjustment("BUY", broker_date=thu, slot_hour=16, primary_source="D_DIRECTION")

        self.assertEqual(sig_mon, "BUY")
        self.assertIsNone(r_mon)
        self.assertEqual(sig_thu, "BUY")
        self.assertIsNone(r_thu)


if __name__ == "__main__":
    unittest.main()
