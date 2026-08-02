"""Install an ephemeral MT4 feed database before the rest of the unittest suite imports bot code."""

import unittest
from pathlib import Path

from repositories import mt4_feed_store
from mt4_feed_test_environment import LIVE_DB_PATH, install_isolated_mt4_feed_database


TEST_DB_PATH = install_isolated_mt4_feed_database()


class MT4FeedDatabaseIsolationTests(unittest.TestCase):
    def test_suite_default_feed_database_is_not_the_live_database(self) -> None:
        self.assertEqual(Path(mt4_feed_store.DB_PATH).resolve(), TEST_DB_PATH.resolve())
        self.assertNotEqual(Path(mt4_feed_store.DB_PATH).resolve(), LIVE_DB_PATH)

    def test_legacy_provider_uses_the_isolated_database(self) -> None:
        import mt5_signal_bot

        provider = mt5_signal_bot.MT4FeedProvider()
        provider_path = Path(provider._db_store._db_path).resolve()
        self.assertEqual(provider_path, TEST_DB_PATH.resolve())

    def test_signal_bot_default_provider_is_mt5(self) -> None:
        import mt5_signal_bot

        self.assertEqual(mt5_signal_bot.MARKET_DATA_PROVIDER.name, "MT5")
        self.assertFalse(hasattr(mt5_signal_bot.MARKET_DATA_PROVIDER, "_db_store"))


if __name__ == "__main__":
    unittest.main()
