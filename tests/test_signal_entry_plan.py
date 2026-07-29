"""Test suite for GBPAUD-driven XAUUSD entry planner and GBPUSD H>=9 inversion (v57)."""
from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


class XauEntryPlanTests(unittest.TestCase):
    """Unit tests for build_xau_entry_plan state machine and rules."""

    def test_h3_same(self) -> None:
        dt = datetime(2026, 7, 29, 3, 0)
        res = mt5_signal_bot.build_xau_entry_plan(dt, 3, "BUY", "TANG")
        self.assertEqual(res["entry_state"], "READY")
        self.assertEqual(res["entry_time"], "03:11")
        self.assertEqual(res["entry_rule"], "H3_SAME")
        self.assertFalse(res["entry_followup_required"])

    def test_h3_opposite_pending(self) -> None:
        dt = datetime(2026, 7, 29, 3, 0)
        res = mt5_signal_bot.build_xau_entry_plan(dt, 3, "BUY", "GIAM")
        self.assertEqual(res["entry_state"], "PENDING_FOLLOWUP")
        self.assertIsNone(res["entry_time"])
        self.assertEqual(res["entry_candidate"], "03:49")
        self.assertTrue(res["entry_followup_required"])

    def test_h3_opposite_then_opposite(self) -> None:
        dt = datetime(2026, 7, 29, 3, 45)
        res = mt5_signal_bot.build_xau_entry_plan(dt, 3, "BUY", "GIAM", followup_gbpaud_direction="GIAM")
        self.assertEqual(res["entry_state"], "READY")
        self.assertEqual(res["entry_time"], "04:49")
        self.assertEqual(res["entry_rule"], "H3_OPPOSITE_THEN_OPPOSITE")

    def test_h3_opposite_then_same(self) -> None:
        dt = datetime(2026, 7, 29, 3, 45)
        res = mt5_signal_bot.build_xau_entry_plan(dt, 3, "BUY", "GIAM", followup_gbpaud_direction="TANG")
        self.assertEqual(res["entry_state"], "READY")
        self.assertEqual(res["entry_time"], "03:49")
        self.assertEqual(res["entry_rule"], "H3_OPPOSITE_THEN_SAME")

    def test_h7_same(self) -> None:
        dt = datetime(2026, 7, 29, 7, 0)
        res = mt5_signal_bot.build_xau_entry_plan(dt, 7, "SELL", "GIAM")
        self.assertEqual(res["entry_state"], "READY")
        self.assertEqual(res["entry_time"], "07:11")
        self.assertEqual(res["entry_rule"], "H7_SAME")

    def test_h7_opposite_pending(self) -> None:
        dt = datetime(2026, 7, 29, 7, 0)
        res = mt5_signal_bot.build_xau_entry_plan(dt, 7, "SELL", "TANG")
        self.assertEqual(res["entry_state"], "PENDING_FOLLOWUP")
        self.assertIsNone(res["entry_time"])
        self.assertEqual(res["entry_candidate"], "07:49")

    def test_h7_opposite_then_opposite(self) -> None:
        dt = datetime(2026, 7, 29, 7, 45)
        res = mt5_signal_bot.build_xau_entry_plan(dt, 7, "SELL", "TANG", followup_gbpaud_direction="TANG")
        self.assertEqual(res["entry_state"], "READY")
        self.assertEqual(res["entry_time"], "08:25")
        self.assertEqual(res["entry_rule"], "H7_OPPOSITE_THEN_OPPOSITE")

    def test_h7_opposite_then_same(self) -> None:
        dt = datetime(2026, 7, 29, 7, 45)
        res = mt5_signal_bot.build_xau_entry_plan(dt, 7, "SELL", "TANG", followup_gbpaud_direction="GIAM")
        self.assertEqual(res["entry_state"], "READY")
        self.assertEqual(res["entry_time"], "07:49")
        self.assertEqual(res["entry_rule"], "H7_OPPOSITE_THEN_SAME")

    def test_h9plus_opposite(self) -> None:
        for hour in (9, 12, 14, 16):
            dt = datetime(2026, 7, 29, hour, 0)
            res = mt5_signal_bot.build_xau_entry_plan(dt, hour, "BUY", "GIAM")
            self.assertEqual(res["entry_state"], "READY")
            self.assertEqual(res["entry_time"], f"{hour:02d}:11")
            self.assertEqual(res["entry_rule"], "H9PLUS_OPPOSITE")

    def test_h9plus_same_pending(self) -> None:
        for hour in (9, 12, 14, 16):
            dt = datetime(2026, 7, 29, hour, 0)
            res = mt5_signal_bot.build_xau_entry_plan(dt, hour, "BUY", "TANG")
            self.assertEqual(res["entry_state"], "PENDING_FOLLOWUP")
            self.assertIsNone(res["entry_time"])
            self.assertEqual(res["entry_candidate"], f"{hour:02d}:49")

    def test_h9plus_same_then_same(self) -> None:
        for hour in (9, 12, 14, 16):
            dt = datetime(2026, 7, 29, hour, 45)
            res = mt5_signal_bot.build_xau_entry_plan(dt, hour, "BUY", "TANG", followup_gbpaud_direction="TANG")
            self.assertEqual(res["entry_state"], "READY")
            self.assertEqual(res["entry_time"], f"{hour + 1:02d}:25")
            self.assertEqual(res["entry_rule"], "H9PLUS_SAME_THEN_SAME")

    def test_h9plus_same_then_opposite(self) -> None:
        for hour in (9, 12, 14, 16):
            dt = datetime(2026, 7, 29, hour, 45)
            res = mt5_signal_bot.build_xau_entry_plan(dt, hour, "BUY", "TANG", followup_gbpaud_direction="GIAM")
            self.assertEqual(res["entry_state"], "READY")
            self.assertEqual(res["entry_time"], f"{hour:02d}:49")
            self.assertEqual(res["entry_rule"], "H9PLUS_SAME_THEN_OPPOSITE")

    def test_gbpusd_h9plus_inversion_in_evaluation(self) -> None:
        """Verify GBPUSD signal is inverted for H>=9 but unchanged for H<9."""
        dt = datetime(2026, 7, 29, 9, 0)
        # Base TANG, pattern BT (GIAM, GIAM, TANG -> BT), prov BUY. offset -15 GIAM (SELL) -> KEEP -> BUY.
        # For GBPUSD H=9: final is inverted to SELL.
        lookback_dirs = ("TANG", "GIAM", "GIAM", "TANG", "GIAM")
        with patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=lookback_dirs):
            res_gbpusd = mt5_signal_bot.evaluate_symbol_m15_for_slot(dt, 9, "GBPUSD")
        self.assertIsNotNone(res_gbpusd)
        self.assertEqual(res_gbpusd["post_offset15_direction"], "BUY")
        self.assertTrue(res_gbpusd["gbpusd_h9plus_inversion_applied"])
        self.assertEqual(res_gbpusd["direction"], "SELL")

        # For H=3, no inversion applied for GBPUSD
        dt3 = datetime(2026, 7, 29, 3, 0)
        with patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=lookback_dirs):
            res_gbpusd_h3 = mt5_signal_bot.evaluate_symbol_m15_for_slot(dt3, 3, "GBPUSD")
        self.assertIsNotNone(res_gbpusd_h3)
        self.assertEqual(res_gbpusd_h3["post_offset15_direction"], "BUY")
        self.assertFalse(res_gbpusd_h3["gbpusd_h9plus_inversion_applied"])
        self.assertEqual(res_gbpusd_h3["direction"], "BUY")


if __name__ == "__main__":
    unittest.main()
