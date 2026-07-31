"""Test D-Direction MISSING retry recomputation (v84)."""
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import mt5_signal_bot


class TestDMissingRetry(unittest.TestCase):
    """Verify MISSING D snapshots trigger retry recomputation without serving stale MISSING state."""

    def setUp(self):
        mt5_signal_bot.clear_d_direction_cache()

    @patch("time.sleep", return_value=None)
    @patch("mt5_signal_bot.build_d_direction_snapshot_v2")
    @patch("mt5_signal_bot.push_d_direction_snapshot")
    @patch("mt5_signal_bot.save_d_direction_snapshot_local")
    @patch("mt5_signal_bot._load_state")
    @patch("mt5_signal_bot._save_state")
    def test_missing_is_retried_until_ready(self, mock_save, mock_load, mock_save_local, mock_push, mock_build, mock_sleep):
        mock_load.return_value = {"d_published_local_dates": {}}
        mock_push.return_value = True

        future_date = (datetime.now(timezone.utc) + timedelta(days=5)).date()

        missing_snapshot = {
            "state": "MISSING",
            "symbols": {"GBPUSD": {"d_state": "MISSING"}, "GBPAUD": {"d_state": "MISSING"}}
        }
        ready_snapshot = {
            "state": "READY",
            "symbols": {"GBPUSD": {"d_state": "READY"}, "GBPAUD": {"d_state": "READY"}}
        }

        # First call returns MISSING, second call returns READY
        mock_build.side_effect = [missing_snapshot, ready_snapshot]

        result = mt5_signal_bot.publish_d_direction_daily(target_local_date=future_date, force=True)

        self.assertEqual(result["state"], "READY")
        self.assertEqual(mock_build.call_count, 2)


if __name__ == "__main__":
    unittest.main()
