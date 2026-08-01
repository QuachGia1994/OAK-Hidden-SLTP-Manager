import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot
from mt5_signal_bot import get_broker_time, set_market_data_provider, MT4FeedProvider, MarketDataClockError


class TestMT4BrokerClockAuthority(unittest.TestCase):

    def setUp(self):
        self._original_provider = mt5_signal_bot.MARKET_DATA_PROVIDER

    def tearDown(self):
        set_market_data_provider(self._original_provider)

    def test_get_broker_time_uses_mt4_provider_when_fresh(self):
        mock_provider = MagicMock()
        mock_health = MagicMock()
        mock_health.fresh = True
        mock_health.state = "fresh"
        mock_provider.get_health.return_value = mock_health
        mock_provider.get_broker_now.return_value = datetime(2026, 7, 31, 14, 2, 0)

        set_market_data_provider(mock_provider)

        b_time = get_broker_time()
        self.assertEqual(b_time, datetime(2026, 7, 31, 14, 2, 0))

    def test_get_broker_time_raises_when_mt4_stale_and_mt5_down(self):
        mock_provider = MagicMock()
        mock_health = MagicMock()
        mock_health.fresh = False
        mock_health.state = "stale"
        mock_provider.get_health.return_value = mock_health

        set_market_data_provider(mock_provider)

        with self.assertRaises(MarketDataClockError):
            get_broker_time()


if __name__ == "__main__":
    unittest.main()
