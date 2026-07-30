import unittest
from datetime import datetime, date, time, timezone, timedelta
from unittest.mock import patch, MagicMock

import mt5_signal_bot
from mt5_signal_bot import (
    get_d_publication_datetime_local,
    get_d_publication_datetime_utc,
    is_d_publication_due,
    build_d_direction_snapshot_v2,
    HO_CHI_MINH_TZ,
    D_PUBLICATION_LOCAL_HOUR,
    D_PUBLICATION_LOCAL_MINUTE,
)


class TestDPublicationEngine(unittest.TestCase):
    def test_d_publication_datetime(self):
        target = date(2026, 7, 31)
        local_dt = get_d_publication_datetime_local(target)
        self.assertEqual(local_dt.year, 2026)
        self.assertEqual(local_dt.month, 7)
        self.assertEqual(local_dt.day, 31)
        self.assertEqual(local_dt.hour, 6)
        self.assertEqual(local_dt.minute, 0)

        utc_dt = get_d_publication_datetime_utc(target)
        self.assertEqual(utc_dt.tzinfo, timezone.utc)
        # 06:00 UTC+7 is 23:00 UTC of previous day (2026-07-30)
        self.assertEqual(utc_dt.strftime("%Y-%m-%d %H:%M:%S"), "2026-07-30 23:00:00")

    def test_is_d_publication_due(self):
        target = date(2026, 7, 31)
        # 05:59:59 local (22:59:59 UTC) -> NOT due
        before = datetime(2026, 7, 30, 22, 59, 59, tzinfo=timezone.utc)
        self.assertFalse(is_d_publication_due(before, target))

        # 06:00:00 local (23:00:00 UTC) -> DUE
        at_due = datetime(2026, 7, 30, 23, 0, 0, tzinfo=timezone.utc)
        self.assertTrue(is_d_publication_due(at_due, target))

        # 06:11:00 local (23:11:00 UTC) -> DUE (Catch-up window)
        after = datetime(2026, 7, 30, 23, 11, 0, tzinfo=timezone.utc)
        self.assertTrue(is_d_publication_due(after, target))

    @patch("mt5_signal_bot.calculate_all_d_directions")
    def test_build_d_direction_snapshot_v2_schema(self, mock_calc):
        mock_calc.return_value = {
            "XAUUSD": {
                "d_direction": "SELL",
                "d_state": "READY",
                "session_date": "2026-07-30",
                "d_candle_open_time": "2026-07-30T19:30:00Z",
                "candle": {"open": 2380.5, "high": 2382.1, "low": 2379.0, "close": 2381.2},
                "d_candle_direction": "GIAM",
            },
            "GBPUSD": {
                "d_direction": "BUY",
                "d_state": "READY",
                "session_date": "2026-07-30",
                "d_candle_open_time": "2026-07-30T19:30:00Z",
                "candle": {"open": 1.2850, "high": 1.2890, "low": 1.2840, "close": 1.2880},
                "d_candle_direction": "TANG",
            },
            "GBPAUD": {
                "d_direction": "BUY",
                "d_state": "READY",
                "session_date": "2026-07-30",
                "d_candle_open_time": "2026-07-30T19:30:00Z",
                "candle": {"open": 1.9500, "high": 1.9550, "low": 1.9490, "close": 1.9540},
                "d_candle_direction": "TANG",
            },
            "GBPJPY": {
                "d_direction": "WAIT",
                "d_state": "DOJI",
                "session_date": "2026-07-30",
                "d_candle_open_time": "2026-07-30T19:30:00Z",
                "candle": {"open": 200.50, "high": 201.00, "low": 200.00, "close": 200.50},
                "d_candle_direction": "DOJI",
            },
            "GBPCAD": {
                "d_direction": "SELL",
                "d_state": "READY",
                "session_date": "2026-07-30",
                "d_candle_open_time": "2026-07-30T19:30:00Z",
                "candle": {"open": 1.7500, "high": 1.7520, "low": 1.7480, "close": 1.7490},
                "d_candle_direction": "GIAM",
            },
        }

        snapshot = build_d_direction_snapshot_v2("2026-07-31", "2026-07-31")
        self.assertEqual(snapshot["schema_version"], 2)
        self.assertEqual(snapshot["target_local_date"], "2026-07-31")
        self.assertEqual(snapshot["publication_timezone"], "Asia/Ho_Chi_Minh")
        self.assertEqual(snapshot["publication_rule"], "DAILY_AT_06_00_LOCAL")
        self.assertEqual(snapshot["state"], "READY")

        # Verify 5 symbols present
        self.assertIn("XAUUSD", snapshot["symbols"])
        self.assertIn("GBPUSD", snapshot["symbols"])
        self.assertIn("GBPAUD", snapshot["symbols"])
        self.assertIn("GBPJPY", snapshot["symbols"])
        self.assertIn("GBPCAD", snapshot["symbols"])

        # Check symbol metadata
        xau = snapshot["symbols"]["XAUUSD"]
        self.assertEqual(xau["d_direction"], "SELL")
        self.assertEqual(xau["price_digits"], 2)
        self.assertEqual(xau["execution_status"], "ON")

        jpy = snapshot["symbols"]["GBPJPY"]
        self.assertEqual(jpy["d_direction"], "WAIT")
        self.assertEqual(jpy["d_state"], "DOJI")
        self.assertEqual(jpy["price_digits"], 3)
        self.assertEqual(jpy["execution_status"], "OFF")


if __name__ == "__main__":
    unittest.main()
