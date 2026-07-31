"""Test Section 28: Weekend & Holiday Fallback for D Direction (v85)."""
import unittest
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import mt5_signal_bot


class TestDWeekendHolidayFallback(unittest.TestCase):
    @patch("mt5_signal_bot.BROKER_CLOCK")
    @patch("mt5_signal_bot.mt5")
    def test_monday_target_selects_friday_h4_20(self, mock_mt5, mock_clock):
        """For Monday target, weekend has no candles, so Friday H4 20:00 is selected."""
        mock_clock.utc_offset_for_date.return_value = 3
        mock_clock.mt5_timestamp_from_broker_datetime.side_effect = lambda dt: int((dt - timedelta(hours=3)).replace(tzinfo=timezone.utc).timestamp())
        mock_clock.broker_datetime_from_mt5_timestamp.side_effect = lambda ts: datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None) + timedelta(hours=3)
        mock_mt5.symbol_select.return_value = True

        monday_target = date(2026, 8, 3)  # Monday
        friday_date = date(2026, 7, 31)   # Friday

        friday_h4_20_utc = datetime(2026, 7, 31, 17, 0, tzinfo=timezone.utc).timestamp()

        def copy_rates_side_effect(symbol, tf, start, end):
            # Sunday / Saturday -> empty
            if start.date() in (date(2026, 8, 2), date(2026, 8, 1)):
                return []
            if start.date() == friday_date:
                return [{"time": friday_h4_20_utc, "open": 1.3400, "high": 1.3450, "low": 1.3390, "close": 1.3440, "tick_volume": 500}]
            return []

        mock_mt5.copy_rates_range.side_effect = copy_rates_side_effect

        candle, sess_date, offset = mt5_signal_bot.find_previous_session_h4_20_candle("GBPUSD", monday_target)

        self.assertIsNotNone(candle)
        self.assertEqual(sess_date, friday_date)


if __name__ == "__main__":
    unittest.main()
