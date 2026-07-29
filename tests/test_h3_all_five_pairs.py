import unittest
from datetime import datetime
import mt5_signal_bot

class TestH3AllFivePairs(unittest.TestCase):
    def test_h3_evaluates_all_five_pairs(self) -> None:
        evaluated = mt5_signal_bot.get_evaluated_pairs_for_hour(3)
        self.assertEqual(evaluated, mt5_signal_bot.SIGNAL_PAIRS)
        self.assertIn("GBPUSD", evaluated)
        self.assertEqual(len(evaluated), 5)

    def test_h3_gbp_entry_plan(self) -> None:
        slot_dt = datetime(2026, 7, 29, 3, 0)
        # Test H:11 entry branch (03:11 -> 04:20)
        plan_h11 = mt5_signal_bot.build_gbp_entry_plan(slot_dt, 3, "READY", "03:11")
        self.assertEqual(plan_h11["pair_entry_times"]["GBPUSD"], "04:20")
        self.assertEqual(plan_h11["pair_entry_states"]["GBPUSD"], "READY")

        # Test H:49 entry branch (03:49 -> 04:20)
        plan_h49 = mt5_signal_bot.build_gbp_entry_plan(slot_dt, 3, "READY", "03:49")
        self.assertEqual(plan_h49["pair_entry_times"]["GBPUSD"], "04:20")
        self.assertEqual(plan_h49["pair_entry_states"]["GBPUSD"], "READY")

        # Test (H+1):25 entry branch (04:25 -> 05:00)
        plan_h25 = mt5_signal_bot.build_gbp_entry_plan(slot_dt, 3, "READY", "04:25")
        self.assertEqual(plan_h25["pair_entry_times"]["GBPUSD"], "05:00")
        self.assertEqual(plan_h25["pair_entry_states"]["GBPUSD"], "READY")

    def test_no_deferred_to_h7_in_bot(self) -> None:
        with open("mt5_signal_bot.py", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("DEFERRED_TO_H7", content)
        self.assertNotIn("GBPUSD_NOT_EVALUATED_AT_H3", content)
