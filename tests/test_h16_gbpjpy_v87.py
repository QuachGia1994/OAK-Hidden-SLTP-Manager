import unittest
from datetime import datetime
from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

from domain.signal_v87 import derive_gbpjpy_signal
import mt5_signal_bot as bot


class H16GBPJPYTests(unittest.TestCase):
    def test_same_relation_reverses_reference(self):
        self.assertEqual(derive_gbpjpy_signal("BUY", "SAME_AS_REFERENCE"), "SELL")

    def test_opposite_relation_follows_reference(self):
        self.assertEqual(derive_gbpjpy_signal("BUY", "OPPOSITE_TO_REFERENCE"), "BUY")

    def test_final_reverse_is_not_part_of_gbpjpy_derivation(self):
        self.assertEqual(derive_gbpjpy_signal("SELL", "SAME_AS_REFERENCE"), "BUY")

    def test_h16_evidence_uses_h1_entry_rule(self):
        record = bot._dashboard_signal_evidence(
            datetime(2026, 8, 3, 16),
            16,
            {
                "logic_version": 87,
                "entry_time": "16:49",
                "entry_state": "READY",
                "timing": {"timeframe": "H1"},
                "pair_evidence": {"XAUUSD": {"evidence_schema_version": 10}},
                "pair_entry_times": {"XAUUSD": "16:49"},
                "pair_entry_states": {"XAUUSD": "READY"},
                "pair_signal_states": {"XAUUSD": "READY"},
            },
        )
        self.assertEqual(record["2026-08-03:16:XAUUSD:v87"]["entry_rule"], "XAUUSD_H1_ENTRY_PLAN")


if __name__ == "__main__":
    unittest.main()
