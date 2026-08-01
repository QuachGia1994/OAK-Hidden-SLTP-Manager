import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt4_feed_server
from repositories.mt4_feed_store import MT4FeedStore


class TestMT4FeedHeartbeat(unittest.TestCase):
    def test_post_heartbeat_and_health_use_feed_server(self):
        handle, path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        try:
            store = MT4FeedStore(db_path=path)
            payload = {
                "source_id": "test_ea",
                "broker_time": "2026-07-31T14:02:00",
                "broker_utc_offset": 3,
                "observed_at_utc": datetime.now(timezone.utc).isoformat(),
                "schema_version": 2,
            }
            with patch.object(mt4_feed_server, "feed_store", store):
                client = mt4_feed_server.app.test_client()
                response = client.post("/mt4-feed/heartbeat", json=payload)
                self.assertEqual(response.status_code, 200)
                health = client.get("/mt4-feed/health")
            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.get_json()["data_state"], "connected")
        finally:
            try:
                store.close()
            except Exception:
                pass
            if os.path.exists(path):
                os.unlink(path)


if __name__ == "__main__":
    unittest.main()
