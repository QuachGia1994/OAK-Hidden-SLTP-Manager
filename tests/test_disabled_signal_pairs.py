import unittest
from datetime import datetime
from unittest.mock import patch
from mt5_signal_bot import evaluate_all_pairs_for_slot

class TestDisabledSignalPairs(unittest.TestCase):
    @patch("mt5_signal_bot.read_completed_m30_candle_by_open_time")
    def test_gbpjpy_gbpcad_are_disabled(self, mock_read):
        def fake_candle(symbol, open_dt, as_of_dt=None):
            return {"open": "2300.0", "close": "2305.0", "high": "2306.0", "low": "2299.0"}

        mock_read.side_effect = fake_candle

        slot_dt = datetime(2026, 7, 30, 7, 0, 0)
        res = evaluate_all_pairs_for_slot(slot_dt, 7)
        self.assertIsNotNone(res)

        pair_signal_states = res["pair_signal_states"]
        pair_entry_states = res["pair_entry_states"]
        pair_labels = res["pair_labels"]

        self.assertEqual(pair_signal_states["GBPJPY"], "DISABLED")
        self.assertEqual(pair_signal_states["GBPCAD"], "DISABLED")
        self.assertEqual(pair_entry_states["GBPJPY"], "DISABLED")
        self.assertEqual(pair_entry_states["GBPCAD"], "DISABLED")
        self.assertEqual(pair_labels["GBPJPY"], "OFF")
        self.assertEqual(pair_labels["GBPCAD"], "OFF")

if __name__ == "__main__":
    unittest.main()
