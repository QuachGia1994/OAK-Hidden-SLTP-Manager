import os
import tempfile
import unittest
from datetime import datetime, timezone, timedelta

from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

from repositories.mt4_feed_store import MT4FeedStore, AmbiguousMT4FeedSourceError
from mt5_signal_bot import MT4FeedProvider


def bar_dict(source_id, broker_open_at, o, h, l, c, utc_open_at=""):
    return {
        "broker_open_at": broker_open_at,
        "utc_open_at": utc_open_at,
        "open": o,
        "high": h,
        "low": l,
        "close": c,
        "is_complete": True,
    }


class TestMT4FeedSourceSelection(unittest.TestCase):

    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.store = MT4FeedStore(db_path=self.temp_db.name)
        self.provider = MT4FeedProvider(feed_store=self.store)

    def tearDown(self):
        self.store.close()
        if os.path.exists(self.temp_db.name):
            os.unlink(self.temp_db.name)

    def _save_heartbeat(self, source_id="ea-1", age_seconds=0, offset=3):
        observed = datetime.now(timezone.utc) - timedelta(seconds=age_seconds)
        self.store.save_heartbeat({
            "source_id": source_id,
            "broker_time": "2026-07-31T14:02:00",
            "broker_utc_offset": offset,
            "observed_at_utc": observed.isoformat(),
            "schema_version": 2,
        })

    def _seed_conflicting_bars(self):
        self.store.save_bars(
            "ea-1", "XAUUSD", "XAUUSD", "H1",
            [bar_dict("ea-1", "2026-07-31 06:00:00", 100, 101, 99, 100)],
        )
        self.store.save_bars(
            "ea-2", "XAUUSD", "XAUUSD", "H1",
            [bar_dict("ea-2", "2026-07-31 06:00:00", 99, 100, 98, 98)],
        )

    def test_fresh_heartbeat_selects_the_active_source(self):
        self._save_heartbeat("ea-1", age_seconds=0)
        self.assertEqual(self.store.get_active_source_id(), "ea-1")
        self.assertEqual(self.provider.get_active_source_id(), "ea-1")

    def test_stale_heartbeat_returns_no_active_source(self):
        self._save_heartbeat("ea-1", age_seconds=90)
        self.assertIsNone(self.store.get_active_source_id())
        self.assertIsNone(self.provider.get_active_source_id())

    def test_wrong_schema_heartbeat_returns_no_active_source(self):
        observed = datetime.now(timezone.utc).isoformat()
        self.store._ensure_open()
        self.store._conn.execute("""
            INSERT OR REPLACE INTO mt4_feed_heartbeat
                (source_id, broker_time, broker_utc_offset, observed_at_utc, schema_version)
            VALUES (?, ?, ?, ?, ?)
        """, ("ea-1", "2026-07-31T14:02:00", 3, observed, 1))
        self.store._conn.commit()
        self.assertIsNone(self.store.get_active_source_id())

    def test_conflicting_ohlc_without_source_id_fails_closed(self):
        self._seed_conflicting_bars()
        with self.assertRaises(AmbiguousMT4FeedSourceError):
            self.store.get_exact_bar("XAUUSD", "H1", "2026-07-31 06:00:00")

    def test_explicit_source_id_returns_that_sources_bar(self):
        self._seed_conflicting_bars()
        bar_ea1 = self.store.get_exact_bar(
            "XAUUSD", "H1", "2026-07-31 06:00:00", source_id="ea-1"
        )
        self.assertEqual(bar_ea1["open_exact"], "100")
        bar_ea2 = self.store.get_exact_bar(
            "XAUUSD", "H1", "2026-07-31 06:00:00", source_id="ea-2"
        )
        self.assertEqual(bar_ea2["open_exact"], "99")

    def test_provider_uses_the_active_source_id(self):
        self._seed_conflicting_bars()
        self._save_heartbeat("ea-2", age_seconds=0)
        bar = self.provider.get_exact_bar(
            "XAUUSD", "H1", datetime(2026, 7, 31, 6, 0, 0)
        )
        self.assertIsNotNone(bar)
        self.assertEqual(bar["source_id"], "ea-2")
        self.assertEqual(bar["open_exact"], "99")

    def test_identical_ohlc_across_sources_resolves_deterministically(self):
        self.store.save_bars(
            "ea-1", "XAUUSD", "XAUUSD", "H1",
            [bar_dict("ea-1", "2026-07-31 06:00:00", 100, 101, 99, 100)],
        )
        self.store.save_bars(
            "ea-2", "XAUUSD", "XAUUSD", "H1",
            [bar_dict("ea-2", "2026-07-31 06:00:00", 100, 101, 99, 100)],
        )
        bar = self.store.get_exact_bar("XAUUSD", "H1", "2026-07-31 06:00:00")
        self.assertIsNotNone(bar)
        self.assertEqual(bar["open_exact"], "100")


if __name__ == "__main__":
    unittest.main()
