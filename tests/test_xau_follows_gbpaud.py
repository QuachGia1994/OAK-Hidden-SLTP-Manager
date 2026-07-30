"""XAU direction follows native GBPAUD while XAU entry follows its own M30 timing."""

import unittest
import mt5_signal_bot

class XauFollowsGbpaudTests(unittest.TestCase):
    def test_h3_h14_h16_reverse_native_gbpaud_signal(self) -> None:
        for hour in (3, 14, 16):
            with self.subTest(hour=hour):
                res = mt5_signal_bot.derive_all_pair_final_signals(hour, "BUY", "BUY")
                self.assertEqual(res["XAUUSD"], "SELL")

    def test_h7_h9_h12_keep_native_gbpaud_signal(self) -> None:
        for hour in (7, 9, 12):
            with self.subTest(hour=hour):
                res = mt5_signal_bot.derive_all_pair_final_signals(hour, "BUY", "BUY")
                self.assertEqual(res["XAUUSD"], "BUY")

    def test_wait_has_no_direction_or_entry_fallback(self) -> None:
        res = mt5_signal_bot.derive_all_pair_final_signals(7, "WAIT", "WAIT")
        self.assertEqual(res["XAUUSD"], "WAIT")

if __name__ == "__main__":
    unittest.main()
