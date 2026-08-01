import os
import tempfile
import unittest
from datetime import datetime, timezone

from repositories.mt4_feed_store import MT4FeedStore


class TestMT4BrokerOffsetHistory(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        handle.close()
        self.path = handle.name
        self.store = MT4FeedStore(db_path=self.path)

    def tearDown(self):
        self.store.close()
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_offsets_are_cached_per_broker_date(self):
        self.store.save_heartbeat({
            "schema_version": 2,
            "source_id": "ea",
            "broker_time": "2026-10-25T14:00:00",
            "broker_utc_offset": 2,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        })
        self.store.save_heartbeat({
            "schema_version": 2,
            "source_id": "ea",
            "broker_time": "2026-10-26T14:00:00",
            "broker_utc_offset": 3,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        })
        self.assertEqual(self.store.get_broker_utc_offset("2026-10-25"), 2)
        self.assertEqual(self.store.get_broker_utc_offset("2026-10-26"), 3)

    def test_large_offset_jump_is_rejected(self):
        self.store.save_heartbeat({
            "schema_version": 2,
            "source_id": "ea",
            "broker_time": "2026-10-25T14:00:00",
            "broker_utc_offset": 2,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        })
        with self.assertRaises(ValueError):
            self.store.save_heartbeat({
                "schema_version": 2,
                "source_id": "ea",
                "broker_time": "2026-10-25T15:00:00",
                "broker_utc_offset": 5,
                "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            })

    def test_missing_offset_has_no_default(self):
        with self.assertRaises(ValueError):
            self.store.get_broker_utc_offset()


if __name__ == "__main__":
    unittest.main()
