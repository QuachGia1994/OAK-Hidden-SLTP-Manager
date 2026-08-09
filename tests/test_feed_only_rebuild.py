"""MT5-only history rebuild contract tests."""
import unittest
from unittest.mock import patch

import mt5_signal_bot


class HistoryRebuildContractTests(unittest.TestCase):
    def test_ready_records_are_complete(self):
        record = {
            "rebuild_state": "READY",
            "pair_signal_states": {"XAUUSD": "READY", "GBPUSD": "READY"},
            "wait_reasons": {},
        }
        self.assertTrue(mt5_signal_bot._compute_rebuild_complete([record]))

    def test_missing_mt5_input_is_not_complete(self):
        record = {
            "rebuild_state": "MISSING_INPUT",
            "incomplete": True,
            "missing_inputs": ["WAIT_MT5_DATA"],
            "pair_signal_states": {"XAUUSD": "WAIT"},
        }
        self.assertFalse(mt5_signal_bot._compute_rebuild_complete([record]))

    def test_wait_record_with_mt5_data_reason_is_not_complete(self):
        record = {
            "rebuild_state": "READY",
            "pair_signal_states": {"XAUUSD": "WAIT"},
            "wait_reasons": {"XAUUSD": "WAIT_MT5_DATA"},
        }
        self.assertFalse(mt5_signal_bot._compute_rebuild_complete([record]))

    def test_rebuild_recent_history_remains_mt5_backed(self):
        with patch.object(mt5_signal_bot, "evaluate_all_pairs_for_slot", return_value={
            "signal": "WAIT",
            "entry_time": None,
            "source_date": "2026-07-31",
            "applicable_pairs": ["XAUUSD"],
            "pair_dirs": {"XAUUSD": "WAIT"},
            "pair_signal_states": {"XAUUSD": "WAIT"},
            "pair_evidence": {},
            "failure_reason": "WAIT_MT5_DATA",
            "d_directions": {},
            "timing": {},
        }):
            record, _ = mt5_signal_bot._build_rebuild_record(__import__("datetime").datetime(2026, 7, 31, 7), 7)
        self.assertEqual(record["rebuild_state"], "MISSING_INPUT")
        self.assertIn("WAIT_MT5_DATA", record["missing_inputs"])


if __name__ == "__main__":
    unittest.main()
