"""Regression tests for the current XAU-only slot matrix."""
from datetime import datetime, timezone
from unittest.mock import patch
import unittest

import mt5_signal_bot
from mt5_signal_bot import calculate_slot_signal, get_pair_direction


class SlotMatrixTests(unittest.TestCase):
    def test_h3_is_disabled(self) -> None:
        broker_dt = datetime(2026, 7, 14, 3, 45, tzinfo=timezone.utc)
        with patch.object(mt5_signal_bot, "_lookup_h5_signal_yesterday", return_value="BUY"):
            result = calculate_slot_signal(broker_dt, 3)
            self.assertEqual(result["signal"], "WAIT")



    def test_h2_and_normal_slots_apply_m5_m30_then_xau_m30(self) -> None:
        broker_dt = datetime(2026, 7, 14, 8, 45, tzinfo=timezone.utc)
        with patch.object(
            mt5_signal_bot,
            "analyze",
            side_effect=lambda *_args: {"signal": "BUY", "report": "pattern", "h1_signal": None},
        ), patch.object(
            mt5_signal_bot, "get_xauusd_m30_signal", return_value="BUY"
        ):
            for hour in (12, 13, 15):
                with self.subTest(hour=hour):
                    result = calculate_slot_signal(broker_dt, hour)
                    self.assertEqual(result["pattern_signal"], "BUY")
                    self.assertEqual(result["signal"], "SELL")
                    self.assertTrue(result["skip_xau_m30"])

    def test_h1500_signal_resolution(self) -> None:
        from mt5_signal_bot import resolve_h1500_signal
        # Normal Mon (wd=0, special=False)
        self.assertEqual(resolve_h1500_signal("SW", "BUY", 0, False), "BUY")
        self.assertEqual(resolve_h1500_signal("BT", "BUY", 0, False), "SELL")
        # Normal Thu/Fri (wd=3, special=False)
        self.assertEqual(resolve_h1500_signal("SW", "BUY", 3, False), "SELL")
        self.assertEqual(resolve_h1500_signal("BT", "BUY", 3, False), "BUY")
        # Special Thu/Fri (wd=3/4, special=True)
        self.assertEqual(resolve_h1500_signal("SW", "BUY", 4, True), "BUY")
        self.assertEqual(resolve_h1500_signal("BT", "BUY", 4, True), "SELL")
        # Special Mon (wd=0, special=True)
        self.assertEqual(resolve_h1500_signal("SW", "BUY", 0, True), "SELL")
        self.assertEqual(resolve_h1500_signal("BT", "BUY", 0, True), "BUY")


if __name__ == "__main__":
    unittest.main()
