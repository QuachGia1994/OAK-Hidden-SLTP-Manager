"""Test Section 7 & 8 & 27: Exact OHLC Fixture Validation & XAUUSD D Mapping (v85)."""
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import mt5_signal_bot


class TestDH4ExactOHLC(unittest.TestCase):
    @patch("mt5_signal_bot.BROKER_CLOCK")
    @patch("mt5_signal_bot.mt5")
    def test_gbpusd_exact_ohlc_fixture(self, mock_mt5, mock_clock):
        """GBPUSD 2026-07-30 H4 20:00: O=1.34646, H=1.34766, L=1.34545, C=1.34639 -> SELL."""
        mock_clock.utc_offset_for_date.return_value = 3
        mock_clock.mt5_timestamp_from_broker_datetime.side_effect = lambda dt: int((dt - timedelta(hours=3)).replace(tzinfo=timezone.utc).timestamp())
        mock_clock.broker_datetime_from_mt5_timestamp.side_effect = lambda ts: datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None) + timedelta(hours=3)
        mock_mt5.symbol_select.return_value = True

        target_broker_date = date(2026, 7, 31)

        # Mock H4 20:00 candle for 2026-07-30
        h4_20_utc = datetime(2026, 7, 30, 17, 0, tzinfo=timezone.utc).timestamp()
        mock_candle = {"time": h4_20_utc, "open": 1.34646, "high": 1.34766, "low": 1.34545, "close": 1.34639, "tick_volume": 500}
        mock_mt5.copy_rates_range.return_value = [mock_candle]

        gbp_res = mt5_signal_bot.calculate_d_direction("GBPUSD", target_broker_date)
        xau_res = mt5_signal_bot.calculate_d_direction("XAUUSD", target_broker_date)

        self.assertEqual(gbp_res["d_direction"], "SELL")
        self.assertEqual(gbp_res["d_state"], "READY")
        self.assertEqual(gbp_res["session_date"], "2026-07-30")

        # XAUUSD uses GBPUSD D
        self.assertEqual(xau_res["d_direction"], "SELL")
        self.assertEqual(xau_res["d_state"], "READY")
        self.assertEqual(xau_res["source_symbol"], "GBPUSD")


if __name__ == "__main__":
    unittest.main()
