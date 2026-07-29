import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import mt5_signal_bot

class TestSignalApiUpsert(unittest.TestCase):
    @patch("mt5_signal_bot.BROKER_CLOCK.utc_offset_for_date", return_value=3)
    @patch("mt5_signal_bot.evaluate_xau_entry_timing_basis_m15", return_value={"entry_basis_direction": "BUY", "entry_time": "03:11"})
    @patch("mt5_signal_bot.evaluate_gbpaud_entry_timing_m15", return_value={"offset15_direction": "BUY"})
    @patch("mt5_signal_bot.derive_all_pair_signals_from_xau_entry", return_value={"XAUUSD": "BUY", "GBPUSD": "BUY", "GBPAUD": "BUY", "GBPJPY": "BUY", "GBPCAD": "BUY"})
    def test_record_revision_and_state_updated_at_in_eval(self, mock_derive, mock_gbpaud, mock_xau, mock_clock):
        dt = datetime(2026, 7, 29, 3, 0)
        res = mt5_signal_bot.evaluate_all_pairs_for_slot(dt, 3)
        self.assertIsNotNone(res)
        self.assertIn("record_revision", res)
        self.assertIn("state_updated_at_utc", res)
        self.assertEqual(res["logic_version"], 70)
        self.assertIsInstance(res["record_revision"], int)

