"""Live loop re-evaluates PENDING_LAYER3 slots after H:30 (v75)."""

import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock

import mt5_signal_bot


class PendingLayer3RestartRecoveryTests(unittest.TestCase):
    """_process_live_slot must re-evaluate PENDING_LAYER3 after H:30."""

    def setUp(self):
        mt5_signal_bot.sent_today.clear()
        mt5_signal_bot.entry_alerts_sent.clear()
        mt5_signal_bot.entry_alerts_pending.clear()

    @patch("mt5_signal_bot._save_state")
    @patch("mt5_signal_bot.push_signal_evidence")
    @patch("mt5_signal_bot.push_to_dashboard")
    @patch("mt5_signal_bot.log_signal")
    @patch("mt5_signal_bot._get_current_entry_state", return_value="PENDING_LAYER3")
    @patch("mt5_signal_bot.calculate_slot_signal")
    def test_recheck_pending_entry_after_h30(
        self, mock_calc, mock_entry_state, _log, _push, _ev, _save
    ):
        mock_calc.return_value = {
            "signal": "BUY",
            "signal_state": "READY",
            "entry_state": "READY",
            "entry_time": "07:49",
            "pair_dirs": {s: "BUY" for s in mt5_signal_bot.SIGNAL_PAIRS},
            "pair_signal_states": {s: "READY" for s in mt5_signal_bot.SIGNAL_PAIRS},
            "pair_entry_states": {s: "READY" for s in mt5_signal_bot.SIGNAL_PAIRS},
            "pair_entry_times": {s: "08:00" for s in mt5_signal_bot.SIGNAL_PAIRS},
        }
        mock_calc.return_value["pair_entry_times"]["XAUUSD"] = "07:49"

        broker_dt = datetime(2026, 7, 30, 7, 35, 0)
        key = (broker_dt.date(), 7)
        mt5_signal_bot.sent_today.add(key)

        result = mt5_signal_bot._process_live_slot(broker_dt, 7)

        mock_calc.assert_called_once()
        self.assertTrue(result)
        self.assertIn(key, mt5_signal_bot.sent_today)

    @patch("mt5_signal_bot._save_state")
    @patch("mt5_signal_bot._get_current_entry_state", return_value="READY")
    def test_skip_sent_slot_with_ready_entry(self, mock_entry_state, _save):
        broker_dt = datetime(2026, 7, 30, 9, 0, 0)
        key = (broker_dt.date(), 7)
        mt5_signal_bot.sent_today.add(key)

        result = mt5_signal_bot._process_live_slot(broker_dt, 7)

        self.assertFalse(result)

    @patch("mt5_signal_bot._save_state")
    @patch("mt5_signal_bot._get_current_entry_state", return_value="PENDING_LAYER3")
    def test_no_recheck_before_h30(self, mock_entry_state, _save):
        broker_dt = datetime(2026, 7, 30, 7, 10, 0)
        key = (broker_dt.date(), 7)
        mt5_signal_bot.sent_today.add(key)

        result = mt5_signal_bot._process_live_slot(broker_dt, 7)

        self.assertFalse(result)


if __name__ == "__main__":
    unittest.main()
