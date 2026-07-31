"""Test Section 9 & 10: Broker to Local GMT+7 Time Conversion (v85)."""
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import mt5_signal_bot


class TestDBrokerLocalConversion(unittest.TestCase):
    @patch("mt5_signal_bot.BROKER_CLOCK")
    @patch("mt5_signal_bot.mt5")
    def test_broker_20_00_converts_to_gmt7_00_00(self, mock_mt5, mock_clock):
        """Broker 20:00 (UTC+3) = UTC 17:00 = GMT+7 00:00 next day (00:00 -> 04:00)."""
        mock_clock.utc_offset_for_date.return_value = 3
        mock_clock.mt5_timestamp_from_broker_datetime.side_effect = lambda dt: int((dt - timedelta(hours=3)).replace(tzinfo=timezone.utc).timestamp())
        mock_clock.broker_datetime_from_mt5_timestamp.side_effect = lambda ts: datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None) + timedelta(hours=3)
        mock_mt5.symbol_select.return_value = True

        target_broker_date = date(2026, 7, 31)
        h4_20_utc = datetime(2026, 7, 30, 17, 0, tzinfo=timezone.utc).timestamp()
        mock_candle = {"time": h4_20_utc, "open": 1.34646, "high": 1.34766, "low": 1.34545, "close": 1.34639, "tick_volume": 500}
        mock_mt5.copy_rates_range.return_value = [mock_candle]

        res = mt5_signal_bot.calculate_d_direction("GBPUSD", target_broker_date)

        self.assertEqual(res["d_candle_open_time_broker"], "20:00")
        self.assertEqual(res["d_candle_close_time_broker"], "00:00")
        self.assertEqual(res["d_candle_open_time_local"], "00:00")
        self.assertEqual(res["d_candle_close_time_local"], "04:00")

        # Verify source_candle_identity structure
        identity = res.get("source_candle_identity")
        self.assertIsNotNone(identity)
        self.assertEqual(identity["canonical_symbol"], "GBPUSD")
        self.assertEqual(identity["open_exact"], "1.34646")


if __name__ == "__main__":
    unittest.main()
