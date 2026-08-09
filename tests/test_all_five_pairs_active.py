"""v87 contract: all five signal pairs remain active."""
import unittest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import mt5_signal_bot


class TestAllFivePairsActive(unittest.TestCase):
    def test_active_pairs_contain_gbpjpy_and_gbpcad(self):
        """ACTIVE_SIGNAL_PAIRS must contain GBPJPY and GBPCAD."""
        self.assertIn("GBPJPY", mt5_signal_bot.ACTIVE_SIGNAL_PAIRS)
        self.assertIn("GBPCAD", mt5_signal_bot.ACTIVE_SIGNAL_PAIRS)
        self.assertEqual(len(mt5_signal_bot.ACTIVE_SIGNAL_PAIRS), 5)

    def test_disabled_pairs_is_empty(self):
        """DISABLED_SIGNAL_PAIRS must be empty."""
        self.assertEqual(len(mt5_signal_bot.DISABLED_SIGNAL_PAIRS), 0)

    def test_evidence_is_single_source_xau(self):
        """v87 keeps one shared XAUUSD Entry evidence document."""
        self.assertEqual(mt5_signal_bot.EVIDENCE_SIGNAL_PAIRS, ("XAUUSD",))


if __name__ == "__main__":
    unittest.main()
