"""Test Section 5 & 6: Nearest Previous Session Resolution & Safety Guard (v85)."""
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import mt5_signal_bot


class TestDNearestPreviousSession(unittest.TestCase):
    @patch("mt5_signal_bot.BROKER_CLOCK")
    @patch("mt5_signal_bot.mt5")
    def test_selects_2026_07_30_for_target_2026_07_31(self, mock_mt5, mock_clock):
        """For target_broker_date = 2026-07-31, previous session must be 2026-07-30."""
        mock_clock.utc_offset_for_date.return_value = 3
        mock_clock.mt5_timestamp_from_broker_datetime.side_effect = lambda dt: int((dt - timedelta(hours=3)).replace(tzinfo=timezone.utc).timestamp())
        mock_clock.broker_datetime_from_mt5_timestamp.side_effect = lambda ts: datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None) + timedelta(hours=3)
        mock_mt5.symbol_select.return_value = True

        target_broker_date = date(2026, 7, 31)

        # Mock H4 20:00 candle for 2026-07-30
        h4_20_utc = datetime(2026, 7, 30, 17, 0, tzinfo=timezone.utc).timestamp()
        mock_candle = {"time": h4_20_utc, "open": 1.34646, "high": 1.34766, "low": 1.34545, "close": 1.34639, "tick_volume": 500}
        mock_mt5.copy_rates_range.return_value = [mock_candle]

        candle, sess_date, offset = mt5_signal_bot.find_previous_session_h4_20_candle("GBPUSD", target_broker_date)

        self.assertIsNotNone(candle)
        self.assertEqual(sess_date, date(2026, 7, 30))
        self.assertNotEqual(sess_date, date(2026, 7, 29))


if __name__ == "__main__":
    unittest.main()
