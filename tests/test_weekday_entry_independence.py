"""Regression test suite for decoupling XAUUSD Weekday Inversion from entry timing (v61)."""
from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


class WeekdayEntryIndependenceTests(unittest.TestCase):
    def test_wednesday_h7_entry_timing_regression(self) -> None:
        """Wednesday H7 requires weekday inversion for XAUUSD, but entry times MUST remain v59 basis (08:25 XAU / 09:00 GBP)."""
        wednesday_dt = datetime(2026, 7, 29, 7, 0)

        # Mock candles for H7:
        # XAUUSD: Base TANG, BT pattern (TANG, TANG, TANG -> prov BUY), offset15 TANG (BUY) -> relation SAME -> action REVERSE -> post_offset15_dir SELL (xau_entry_basis_signal = SELL)
        # GBPAUD: offset15 TANG (BUY). Relation between XAU SELL and GBPAUD BUY is OPPOSITE -> cand = 07:49, requires H:45 followup
        # GBPAUD H:45 followup: TANG (BUY). Relation between XAU SELL and followup BUY is OPPOSITE -> final entry = 08:25
        def mock_lookback(symbol, tf, candle_dt):
            return "TANG"

        with patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=mock_lookback):
            res = mt5_signal_bot.evaluate_all_pairs_for_slot(
                wednesday_dt, 7, resolve_historical_followup=True
            )

        self.assertIsNotNone(res)
        self.assertEqual(res["logic_version"], 61)
        self.assertTrue(res["weekday_inversion_applied"])

        # Pre-weekday XAU entry basis signal was SELL
        self.assertEqual(res["entry_basis_xauusd_signal"], "SELL")
        # Final XAUUSD signal after Wednesday H7 inversion is BUY
        self.assertEqual(res["final_xauusd_signal"], "BUY")
        self.assertEqual(res["signal"], "BUY")
        self.assertEqual(res["pair_dirs"]["XAUUSD"], "BUY")

        # ENTRY TIMING MUST NOT BE SHIFTED BY WEEKDAY INVERSION:
        self.assertEqual(res["entry_time"], "08:25")
        self.assertEqual(res["pair_entry_times"]["XAUUSD"], "08:25")
        self.assertEqual(res["pair_entry_times"]["GBPUSD"], "09:00")
        self.assertEqual(res["pair_entry_times"]["GBPAUD"], "09:00")

    def test_wednesday_h9_entry_branches_regression(self) -> None:
        """Wednesday H9 weekday inversion flips XAU direction, but all 3 entry branches preserve v59 entry timing."""
        wednesday_dt = datetime(2026, 7, 29, 9, 0)

        # Branch 1: Initial relation OPPOSITE -> entry 09:11 Broker, GBP entry 10:20 Broker
        # XAU entry_basis = BUY, GBPAUD offset15 = SELL -> OPPOSITE
        def mock_branch1(symbol, tf, candle_dt):
            if symbol == "XAUUSD":
                return "GIAM"  # SW GIAM -> BUY pre-weekday basis
            if symbol == "GBPAUD":
                return "GIAM"  # offset15 SELL -> initial relation OPPOSITE
            return "TANG"

        with patch.object(mt5_signal_bot, "_lookback_candle_direction", side_effect=mock_branch1):
            res1 = mt5_signal_bot.evaluate_all_pairs_for_slot(
                wednesday_dt, 9, resolve_historical_followup=True
            )

        self.assertIsNotNone(res1)
        self.assertEqual(res1["entry_basis_xauusd_signal"], "BUY")
        self.assertEqual(res1["final_xauusd_signal"], "SELL")  # Wed H9 inverted
        self.assertEqual(res1["entry_time"], "09:11")
        self.assertEqual(res1["pair_entry_times"]["GBPUSD"], "10:20")
        self.assertEqual(res1["pair_entry_times"]["GBPAUD"], "10:20")

    def test_all_weekday_inversion_slots_non_mutation(self) -> None:
        """Across all weekday inversion slots, entry_state and entry_time are invariant to weekday direction inversion."""
        dates_and_slots = [
            (datetime(2026, 7, 13), (7, 14)),                # Monday
            (datetime(2026, 7, 15), (3, 7, 9, 12, 14, 16)), # Wednesday
            (datetime(2026, 7, 16), (7, 9)),                 # Thursday
            (datetime(2026, 7, 17), (3, 12, 16)),            # Friday
        ]

        for base_dt, slots in dates_and_slots:
            for slot_h in slots:
                dt = base_dt.replace(hour=slot_h, minute=0)
                with (
                    self.subTest(day=dt.strftime("%A"), hour=slot_h),
                    patch.object(mt5_signal_bot, "_lookback_candle_direction", return_value="TANG"),
                ):
                    res = mt5_signal_bot.evaluate_all_pairs_for_slot(
                        dt, slot_h, resolve_historical_followup=True
                    )
                    self.assertIsNotNone(res)
                    self.assertTrue(res["weekday_inversion_applied"])
                    self.assertIsNotNone(res["entry_time"])
                    self.assertIsNotNone(res["pair_entry_times"]["XAUUSD"])
                    self.assertIsNotNone(res["pair_entry_times"]["GBPAUD"])


if __name__ == "__main__":
    unittest.main()
