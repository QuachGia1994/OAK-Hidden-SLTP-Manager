import unittest
import tempfile
import os
from datetime import datetime, timezone, timedelta
from mt4_mt5_server import app, feed_store
from repositories.mt4_feed_store import MT4FeedStore


class TestMT4FeedHeartbeat(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.store = MT4FeedStore(db_path=self.temp_db.name)

    def tearDown(self):
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_post_heartbeat_and_freshness_calculation(self):
        now_utc = datetime.now(timezone.utc)
        hb_fresh = {
            "source_id": "test_ea",
            "broker_time": "2026-07-31T14:02:00",
            "broker_utc_offset": 3,
            "observed_at_utc": now_utc.isoformat(),
            "schema_version": 2,
        }
        self.store.save_heartbeat(hb_fresh)

        fetched = self.store.get_latest_heartbeat("test_ea")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["source_id"], "test_ea")


if __name__ == "__main__":
    unittest.main()
