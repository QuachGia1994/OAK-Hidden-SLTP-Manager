"""Test H4 loading under Windows / system GMT+7 timezone (v84)."""
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestH4WindowsTimezone(unittest.TestCase):
    """Verify H4 20:00 finder uses canonical aware datetimes independently of local OS tz."""

    @patch("mt5_signal_bot.BROKER_CLOCK")
    @patch("mt5_signal_bot.get_candle_by_ts")
    def test_h4_20_candidate_encoding_under_gmt7(self, mock_get_ts, mock_clock):
        from mt5_signal_bot import find_previous_session_h4_20_candle

        target_date = datetime(2026, 7, 31).date()
        mock_clock.utc_offset_for_date.return_value = 3

        expected_broker_open = datetime(2026, 7, 30, 20, 0, 0)
        expected_utc = datetime(2026, 7, 30, 17, 0, 0, tzinfo=timezone.utc)
        expected_ts = int(expected_utc.timestamp())

        mock_clock.mt5_timestamp_from_broker_datetime.return_value = expected_ts
        mock_clock.broker_datetime_from_mt5_timestamp.return_value = expected_broker_open

        mock_candle = {
            "open": 1.2500,
            "high": 1.2550,
            "low": 1.2490,
            "close": 1.2530,
            "time": expected_ts,
        }
        mock_get_ts.return_value = mock_candle

        candle, session_date, offset = find_previous_session_h4_20_candle("GBPUSD", target_date)
        self.assertIsNotNone(candle)
        self.assertEqual(session_date, datetime(2026, 7, 30).date())
        self.assertEqual(offset, 3)


if __name__ == "__main__":
    unittest.main()
