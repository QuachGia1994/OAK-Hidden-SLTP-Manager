"""Test current-day slot rebuild when D transitions to READY (v84)."""
import unittest
from datetime import datetime
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot


class TestDReadyRebuildsCurrentSlots(unittest.TestCase):
    """Verify past slots in current session rebuild when D becomes READY."""

    @patch("mt5_signal_bot._build_rebuild_record")
    @patch("mt5_signal_bot._write_signals_log_atomic")
    @patch("mt5_signal_bot.calculate_all_d_directions")
    def test_rebuild_current_day_slots_triggers_for_passed_hours(self, mock_calc_d, mock_write_log, mock_build_rec):
        mock_calc_d.return_value = {
            "GBPUSD": {"d_direction": "BUY", "d_state": "READY"},
            "GBPAUD": {"d_direction": "SELL", "d_state": "READY"},
            "XAUUSD": {"d_direction": "BUY", "d_state": "READY"},
        }
        mock_build_rec.return_value = (
            {
                "date": "2026-07-31",
                "hour": 3,
                "signal": "BUY",
                "entry_state": "READY",
                "pair_dirs": {"XAUUSD": "BUY"},
            },
            None,
        )

        broker_dt = datetime(2026, 7, 31, 8, 0, 0)
        rebuilt_count = mt5_signal_bot.rebuild_current_day_slots_after_d_ready(broker_dt)

        # At H=8, H3 and H7 slots have passed
        self.assertTrue(mock_build_rec.called)
        self.assertTrue(mock_write_log.called)


if __name__ == "__main__":
    unittest.main()
