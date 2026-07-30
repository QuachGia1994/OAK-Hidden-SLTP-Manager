"""Canonical cross-mapping matrix: GBPUSD follows XAUUSD at H3/H7/H9 (v76)."""

import unittest
from datetime import datetime

from mt5_signal_bot import derive_all_pair_final_signals, next_full_hour_after_signal_slot


class CrossPairSignalMappingTests(unittest.TestCase):
    def test_h3_gbpusd_follows_xauusd(self):
        res = derive_all_pair_final_signals(3, "BUY", "BUY")
        self.assertEqual(res["XAUUSD"], "SELL")
        self.assertEqual(res["GBPAUD"], "SELL")
        self.assertEqual(res["GBPUSD"], "SELL")

    def test_h7_gbpusd_follows_xauusd(self):
        res = derive_all_pair_final_signals(7, "SELL", "BUY")
        self.assertEqual(res["XAUUSD"], "BUY")
        self.assertEqual(res["GBPAUD"], "SELL")
        self.assertEqual(res["GBPUSD"], "BUY")

    def test_h9_gbpusd_follows_xauusd(self):
        res = derive_all_pair_final_signals(9, "BUY", "SELL")
        self.assertEqual(res["XAUUSD"], "SELL")
        self.assertEqual(res["GBPAUD"], "BUY")
        self.assertEqual(res["GBPUSD"], "SELL")

    def test_h12_gbpusd_uses_native(self):
        res = derive_all_pair_final_signals(12, "SELL", "BUY")
        self.assertEqual(res["XAUUSD"], "BUY")
        self.assertEqual(res["GBPAUD"], "SELL")
        self.assertEqual(res["GBPUSD"], "SELL")

    def test_h14_gbpusd_uses_native(self):
        res = derive_all_pair_final_signals(14, "BUY", "BUY")
        self.assertEqual(res["XAUUSD"], "SELL")
        self.assertEqual(res["GBPAUD"], "SELL")
        self.assertEqual(res["GBPUSD"], "BUY")

    def test_h16_gbpusd_uses_native(self):
        res = derive_all_pair_final_signals(16, "SELL", "SELL")
        self.assertEqual(res["XAUUSD"], "BUY")
        self.assertEqual(res["GBPAUD"], "BUY")
        self.assertEqual(res["GBPUSD"], "SELL")

    def test_wait_native_gbpaud_propagates_to_xauusd(self):
        res = derive_all_pair_final_signals(7, "BUY", "WAIT")
        self.assertEqual(res["XAUUSD"], "WAIT")

    def test_wait_native_gbpusd_propagates_to_gbpaud(self):
        res = derive_all_pair_final_signals(7, "WAIT", "BUY")
        self.assertEqual(res["GBPAUD"], "WAIT")

    def test_gbp_entry_schedule_is_next_full_hour(self):
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 3, 0)), "04:00")
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 7, 0)), "08:00")
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 9, 0)), "10:00")
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 12, 0)), "13:00")
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 14, 0)), "15:00")
        self.assertEqual(next_full_hour_after_signal_slot(datetime(2026, 7, 30, 16, 0)), "17:00")


if __name__ == "__main__":
    unittest.main()
