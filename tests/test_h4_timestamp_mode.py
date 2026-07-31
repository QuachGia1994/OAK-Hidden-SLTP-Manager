"""Test BrokerClock broker_datetime_from_mt5_timestamp decoder method (v84)."""
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from domain.broker_clock import BrokerClock


class TestH4TimestampMode(unittest.TestCase):
    """Verify broker_datetime_from_mt5_timestamp decodes timestamps correctly."""

    def test_utc_mode_decoding(self):
        mock_mt5 = MagicMock()
        clock = BrokerClock(mt5_module=mock_mt5)
        clock._timestamp_mode = "utc"
        clock.current_utc_offset = MagicMock(return_value=3)
        clock.utc_offset_for_date = MagicMock(return_value=3)

        # MT5 timestamp = 17:00 UTC on 2026-07-30
        utc_dt = datetime(2026, 7, 30, 17, 0, 0, tzinfo=timezone.utc)
        ts = int(utc_dt.timestamp())

        decoded = clock.broker_datetime_from_mt5_timestamp(ts)
        self.assertEqual(decoded, datetime(2026, 7, 30, 20, 0, 0))

    def test_broker_wall_mode_decoding(self):
        mock_mt5 = MagicMock()
        clock = BrokerClock(mt5_module=mock_mt5)
        clock._timestamp_mode = "broker_wall"

        # MT5 timestamp encodes 20:00 wall time as UTC timestamp epoch
        wall_dt = datetime(2026, 7, 30, 20, 0, 0, tzinfo=timezone.utc)
        ts = int(wall_dt.timestamp())

        decoded = clock.broker_datetime_from_mt5_timestamp(ts)
        self.assertEqual(decoded, datetime(2026, 7, 30, 20, 0, 0))


if __name__ == "__main__":
    unittest.main()
