import os
import tempfile
import unittest
from datetime import datetime, timezone
from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

from mt5_signal_bot import MT4FeedProvider
from repositories.mt4_feed_store import MT4FeedStore

class TestMT4MarketDataProvider(unittest.TestCase):
    def setUp(self):
        self._temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self._temp_db.close()
        self._feed_store = MT4FeedStore(db_path=self._temp_db.name)
        self.provider = MT4FeedProvider(feed_store=self._feed_store)

    def tearDown(self):
        self._feed_store.close()
        if os.path.exists(self._temp_db.name):
            os.unlink(self._temp_db.name)

    def test_provider_name_is_mt4(self):
        self.assertEqual(self.provider.name, "MT4")

    def test_register_and_get_bars(self):
        b_dt = datetime(2026, 7, 30, 20, 0, tzinfo=timezone.utc)
        bar = {"broker_dt": b_dt, "open": 1.34646, "high": 1.34766, "low": 1.34545, "close": 1.34639}
        self.provider.register_bars("GBPUSD", "H4", [bar])

        res_exact = self.provider.get_exact_bar("GBPUSD", "H4", b_dt)
        self.assertIsNotNone(res_exact)
        self.assertEqual(res_exact["open"], 1.34646)

        res_bars = self.provider.get_bars("GBPUSD", "H4", b_dt, b_dt)
        self.assertEqual(len(res_bars), 1)

        res_empty = self.provider.get_bars("XAUUSD", "H4", b_dt, b_dt)
        self.assertEqual(len(res_empty), 0)

if __name__ == "__main__":
    unittest.main()
