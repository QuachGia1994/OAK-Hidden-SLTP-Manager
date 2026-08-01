import unittest
import os
import tempfile
from datetime import datetime, timezone
from repositories.mt4_feed_store import MT4FeedStore


class TestMT4FeedPersistence(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.store = MT4FeedStore(db_path=self.temp_db.name)

    def tearDown(self):
        self.store.close()
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def test_save_and_retrieve_heartbeat(self):
        hb = {
            "source_id": "ea_vantage",
            "account": "123456",
            "server": "Vantage-Live",
            "broker_time": "2026-07-31T14:02:00",
            "broker_utc_offset": 3,
            "observed_at_utc": "2026-07-31T11:02:00Z",
            "last_sequence": 10,
            "schema_version": 2,
        }
        self.store.save_heartbeat(hb)

        fetched = self.store.get_latest_heartbeat("ea_vantage")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["broker_time"], "2026-07-31T14:02:00")
        self.assertEqual(fetched["broker_utc_offset"], 3)

    def test_save_and_retrieve_bars_persisted_across_restart(self):
        bars = [
            {
                "broker_open_at": "2026-07-31 14:00:00",
                "utc_open_at": "2026-07-31T11:00:00+00:00",
                "open": 1.3460,
                "high": 1.3470,
                "low": 1.3450,
                "close": 1.3465,
                "tick_volume": 120,
                "is_complete": True,
            }
        ]
        inserted = self.store.save_bars("ea_vantage", "GBPUSD", "GBPUSD", "M30", bars)
        self.assertEqual(inserted, 1)

        # Simulate restart by creating new store instance reading same db
        new_store = MT4FeedStore(db_path=self.temp_db.name)
        retrieved = new_store.get_bars("GBPUSD", "M30", "2026-07-31 13:30:00", "2026-07-31 14:30:00")
        self.assertEqual(len(retrieved), 1)
        self.assertEqual(retrieved[0]["close"], 1.3465)
        self.assertEqual(retrieved[0]["time"], int(datetime(2026, 7, 31, 11, tzinfo=timezone.utc).timestamp()))

    def test_normalizes_mt4_dot_datetime_format(self):
        self.store.save_heartbeat({
            "schema_version": 2,
            "source_id": "ea_dot",
            "broker_time": "2026.08.03 09:00:05",
            "broker_time_utc": "2026.08.03 06:00:05",
            "broker_utc_offset": 3,
            "observed_at_utc": "2026.08.03 06:00:05",
        })
        self.store.save_bars("ea_dot", "XAUUSD", "XAUUSD.m", "M30", [{
            "broker_open_at": "2026.08.03 08:30:00",
            "open": "2400.10", "high": "2401.10", "low": "2399.90", "close": "2400.80",
            "is_complete": True,
        }])
        self.assertEqual(self.store.get_broker_utc_offset(), 3)
        bar = self.store.get_exact_bar("XAUUSD", "M30", "2026-08-03 08:30:00")
        self.assertEqual(bar["broker_dt"].hour, 8)
        self.assertEqual(bar["utc_open_at"], "2026-08-03T05:30:00Z")

    def test_missing_offset_does_not_guess_utc_timestamp(self):
        self.store.save_bars("ea_without_clock", "XAUUSD", "XAUUSD", "M30", [{
            "broker_open_at": "2026-08-03 08:30:00",
            "open": "2400.10", "high": "2401.10", "low": "2399.90", "close": "2400.80",
            "is_complete": True,
        }])
        bar = self.store.get_exact_bar("XAUUSD", "M30", "2026-08-03 08:30:00")
        self.assertEqual(bar["time"], 0)
        self.assertEqual(bar["utc_open_at"], "")


if __name__ == "__main__":
    unittest.main()
