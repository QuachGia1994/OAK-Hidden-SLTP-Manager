import unittest
from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot

class TestH3AllFivePairs(unittest.TestCase):
    def test_h3_evaluates_all_five_pairs(self) -> None:
        evaluated = mt5_signal_bot.get_evaluated_pairs_for_hour(3)
        self.assertEqual(evaluated, mt5_signal_bot.SIGNAL_PAIRS)
        self.assertIn("GBPUSD", evaluated)
        self.assertEqual(len(evaluated), 5)

    def test_entry_timing_symbols_include_all_pairs(self) -> None:
        """All 5 symbols run independent entry timing in v82."""
        self.assertEqual(
            mt5_signal_bot.ENTRY_TIMING_SYMBOLS,
            ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD"),
        )

    def test_no_deferred_gbp_import(self) -> None:
        """deferred_gbp_entry_time is no longer imported in the bot."""
        self.assertFalse(
            hasattr(mt5_signal_bot, "deferred_gbp_entry_time"),
            "deferred_gbp_entry_time should not be imported in bot module",
        )

    def test_no_deferred_to_h7_in_bot(self) -> None:
        with open("mt5_signal_bot.py", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("DEFERRED_TO_H7", content)
        self.assertNotIn("GBPUSD_NOT_EVALUATED_AT_H3", content)
