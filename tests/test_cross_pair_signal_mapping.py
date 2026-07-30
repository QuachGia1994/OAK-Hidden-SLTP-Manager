import unittest
from mt5_signal_bot import derive_all_pair_final_signals, next_full_hour_after_signal_slot
from datetime import datetime

class TestCrossPairSignalMapping(unittest.TestCase):
    def test_h7_cross_mapping(self):
        # native GBPUSD=BUY, native GBPAUD=BUY
        # H7: XAU = native GBPAUD = BUY
        # GBPAUD = native GBPUSD = BUY
        # GBPUSD = final XAU = BUY
        res = derive_all_pair_final_signals(7, "BUY", "BUY")
        self.assertEqual(res["XAUUSD"], "BUY")
        self.assertEqual(res["GBPAUD"], "BUY")
        self.assertEqual(res["GBPUSD"], "BUY")
        self.assertEqual(res["GBPJPY"], "WAIT")
        self.assertEqual(res["GBPCAD"], "WAIT")

    def test_h14_cross_mapping(self):
        # native GBPUSD=BUY, native GBPAUD=BUY
        # H14: XAU = reverse(native GBPAUD) = SELL
        # GBPAUD = reverse(native GBPUSD) = SELL
        # GBPUSD = native GBPUSD = BUY
        res = derive_all_pair_final_signals(14, "BUY", "BUY")
        self.assertEqual(res["XAUUSD"], "SELL")
        self.assertEqual(res["GBPAUD"], "SELL")
        self.assertEqual(res["GBPUSD"], "BUY")

    def test_gbp_entry_schedule_is_next_full_hour(self):
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 3, 0)), "04:00")
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 7, 0)), "08:00")
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 9, 0)), "10:00")
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 12, 0)), "13:00")
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 14, 0)), "15:00")
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 16, 0)), "17:00")

if __name__ == "__main__":
    unittest.main()
