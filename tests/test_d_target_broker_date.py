"""Test Section 26: Target Broker Date Resolution for D Publication (v85)."""
import unittest
from datetime import datetime, date, timezone, timedelta
from unittest.mock import MagicMock
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

from mt5_signal_bot import resolve_target_broker_date_for_d, get_d_publication_datetime_utc


class TestDTargetBrokerDate(unittest.TestCase):
    def test_target_broker_date_resolution_utc_plus3(self):
        """06:00 GMT+7 on 2026-07-31 -> 23:00 UTC -> 02:00 Broker (2026-07-31)."""
        target_local_date = date(2026, 7, 31)
        mock_clock = MagicMock()
        mock_clock.utc_offset_for_date.return_value = 3
        # 23:00 UTC + 3h = 02:00 Broker on 2026-07-31
        mock_clock.broker_from_utc_datetime.side_effect = lambda utc_dt: (utc_dt + timedelta(hours=3)).replace(tzinfo=None)

        target_broker_date = resolve_target_broker_date_for_d(target_local_date, mock_clock)

        self.assertEqual(target_broker_date, date(2026, 7, 31))
        self.assertNotEqual(target_broker_date, date(2026, 7, 30))

    def test_publication_utc_conversion(self):
        """2026-07-31 06:00 GMT+7 = 2026-07-30 23:00 UTC."""
        pub_utc = get_d_publication_datetime_utc(date(2026, 7, 31))
        self.assertEqual(pub_utc.year, 2026)
        self.assertEqual(pub_utc.month, 7)
        self.assertEqual(pub_utc.day, 30)
        self.assertEqual(pub_utc.hour, 23)
        self.assertEqual(pub_utc.minute, 0)


if __name__ == "__main__":
    unittest.main()
