import unittest
import mt5_signal_bot

class TestH3AllFivePairs(unittest.TestCase):
    def test_h3_evaluates_all_five_pairs(self) -> None:
        evaluated = mt5_signal_bot.get_evaluated_pairs_for_hour(3)
        self.assertEqual(evaluated, mt5_signal_bot.SIGNAL_PAIRS)
        self.assertIn("GBPUSD", evaluated)
        self.assertEqual(len(evaluated), 5)

    def test_h3_gbp_entry_plan(self) -> None:
        self.assertEqual(mt5_signal_bot.deferred_gbp_entry_time("03:11"), "04:00")
        self.assertEqual(mt5_signal_bot.deferred_gbp_entry_time("03:49"), "04:00")
        self.assertEqual(mt5_signal_bot.deferred_gbp_entry_time("04:49"), "05:00")

    def test_no_deferred_to_h7_in_bot(self) -> None:
        with open("mt5_signal_bot.py", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("DEFERRED_TO_H7", content)
        self.assertNotIn("GBPUSD_NOT_EVALUATED_AT_H3", content)
