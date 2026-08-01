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

    def test_historical_bar_utc_timestamp_derives_and_caches_its_offset(self):
        self.store.save_bars("ea", "GBPJPY", "GBPJPY", "H4", [{
            "broker_open_at": "2026-07-30 20:00:00",
            "utc_open_at": "2026-07-30T17:00:00Z",
            "open": "214.851", "high": "215.139", "low": "213.459", "close": "214.794",
            "is_complete": True,
        }])

        self.assertEqual(self.store.get_broker_utc_offset("2026-07-30"), 3)
        cached = self.store.get_clock_offset_history("ea")
        self.assertTrue(any(row["broker_date"] == "2026-07-30" and row["broker_utc_offset"] == 3 for row in cached))

    def test_conflicting_historical_bar_offsets_are_rejected(self):
        self.store.save_bars("ea", "GBPJPY", "GBPJPY", "H4", [{
            "broker_open_at": "2026-07-30 20:00:00",
            "utc_open_at": "2026-07-30T17:00:00Z",
            "open": "214.851", "high": "215.139", "low": "213.459", "close": "214.794",
            "is_complete": True,
        }, {
            "broker_open_at": "2026-07-30 21:00:00",
            "utc_open_at": "2026-07-30T20:00:00Z",
            "open": "214.794", "high": "215.000", "low": "214.000", "close": "214.500",
            "is_complete": True,
        }])

        with self.assertRaises(ValueError):
            self.store.get_broker_utc_offset("2026-07-30")


if __name__ == "__main__":
    unittest.main()
