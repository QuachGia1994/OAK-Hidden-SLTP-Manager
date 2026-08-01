import unittest
import tempfile
import os
from datetime import datetime, timedelta, timezone
from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

from mt5_signal_bot import MT4FeedProvider, MarketDataClockError
from repositories.mt4_feed_store import MT4FeedStore


class TestMT4ProviderIntegration(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.db_store = MT4FeedStore(db_path=self.temp_db.name)
        self.provider = MT4FeedProvider(feed_store=self.db_store)

    def tearDown(self):
        self.db_store.close()
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_provider_health_and_broker_clock_from_sqlite(self):
        now_utc = datetime.now(timezone.utc)
        hb = {
            "source_id": "ea1",
            "broker_time": "2026-07-31T14:02:00",
            "broker_utc_offset": 3,
            "observed_at_utc": now_utc.isoformat(),
            "schema_version": 2,
        }
        self.db_store.save_heartbeat(hb)

        health = self.provider.get_health()
        self.assertTrue(health.fresh)
        self.assertEqual(health.state, "connected")

        b_now = self.provider.get_broker_now()
        self.assertEqual(b_now.hour, 14)
        self.assertEqual(b_now.minute, 2)

    def test_degraded_heartbeat_cannot_supply_a_live_signal_clock(self):
        observed_at = datetime.now(timezone.utc) - timedelta(seconds=20)
        self.db_store.save_heartbeat({
            "source_id": "ea1",
            "broker_time": "2026-07-31T14:02:00",
            "broker_utc_offset": 3,
            "observed_at_utc": observed_at.isoformat(),
            "schema_version": 2,
        })

        health = self.provider.get_health()

        self.assertEqual(health.state, "degraded")
        self.assertFalse(health.fresh)
        with self.assertRaises(MarketDataClockError):
            self.provider.get_broker_now()


if __name__ == "__main__":
    unittest.main()
