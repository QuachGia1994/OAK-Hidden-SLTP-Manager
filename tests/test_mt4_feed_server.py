import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import mt4_feed_server
from repositories.mt4_feed_store import MT4FeedStore


class TestMT4FeedServer(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.store = MT4FeedStore(db_path=self.temp_db.name)
        self.original_store = mt4_feed_server.feed_store
        mt4_feed_server.feed_store = self.store
        self.client = mt4_feed_server.app.test_client()

    def tearDown(self):
        mt4_feed_server.feed_store = self.original_store
        self.store.close()
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_heartbeat_and_bars_round_trip(self):
        heartbeat = {
            "schema_version": 2,
            "source_id": "ea-test",
            "broker_time": "2026-08-01T14:00:00",
            "broker_time_utc": "2026-08-01T11:00:00",
            "broker_utc_offset": 3,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "last_sequence": 1,
        }
        response = self.client.post("/mt4-feed/heartbeat", json=heartbeat)
        self.assertEqual(response.status_code, 200)

        payload = {
            "schema_version": 2,
            "source_id": "ea-test",
            "symbol": "XAUUSD",
            "resolved_symbol": "XAUUSD",
            "timeframe": "M30",
            "bars": [{
                "broker_open_at": "2026-08-01 13:30:00",
                "broker_close_at": "2026-08-01 14:00:00",
                "open": "2400.10",
                "high": "2401.20",
                "low": "2399.90",
                "close": "2400.80",
                "tick_volume": 42,
                "is_complete": True,
            }],
        }
        response = self.client.post("/mt4-feed/bars", json=payload)
        self.assertEqual(response.status_code, 200)
        response = self.client.get(
            "/mt4-feed/bars?symbol=XAUUSD&timeframe=M30&start=2026-08-01%2013:00:00&end=2026-08-01%2014:00:00"
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["bars"][0]["close_exact"], "2400.80")

    def test_incomplete_or_wrong_schema_is_rejected(self):
        response = self.client.post("/mt4-feed/heartbeat", json={"schema_version": 1})
        self.assertEqual(response.status_code, 400)
        response = self.client.post(
            "/mt4-feed/bars",
            json={"schema_version": 2, "symbol": "XAUUSD", "timeframe": "M30", "bars": [{"is_complete": False}]},
        )
        self.assertEqual(response.status_code, 400)

    def test_feed_token_is_enforced_when_configured(self):
        heartbeat = {
            "schema_version": 2,
            "source_id": "ea-test",
            "broker_time": "2026-08-01T14:00:00",
            "broker_time_utc": "2026-08-01T11:00:00",
            "broker_utc_offset": 3,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "last_sequence": 1,
        }
        with patch.dict(os.environ, {"MT4_FEED_TOKEN": "secret"}, clear=False):
            self.assertEqual(self.client.post("/mt4-feed/heartbeat", json=heartbeat).status_code, 401)
            response = self.client.post(
                "/mt4-feed/heartbeat",
                json=heartbeat,
                headers={"X-MT4-FEED-TOKEN": "secret"},
            )
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
