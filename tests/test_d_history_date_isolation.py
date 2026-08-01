import unittest
import os
import tempfile
from datetime import date, datetime, timezone

from mt5_signal_bot import MT4FeedProvider, build_d_direction_snapshot_for_date
from repositories.mt4_feed_store import MT4FeedStore


class TestDHistoryDateIsolation(unittest.TestCase):
    def test_each_target_date_selects_its_own_previous_session(self):
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_db.close()
        store = MT4FeedStore(db_path=temp_db.name)
        self.addCleanup(store.close)
        self.addCleanup(lambda: os.path.exists(temp_db.name) and os.unlink(temp_db.name))
        provider = MT4FeedProvider(feed_store=store)
        for heartbeat_date in ("2026-07-29", "2026-07-30", "2026-07-31"):
            store.save_heartbeat({
                "schema_version": 2,
                "source_id": "test-ea",
                "broker_time": f"{heartbeat_date}T14:00:00",
                "broker_utc_offset": 3,
                "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            })
        for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD"):
            for session_date, opening, closing in (
                (date(2026, 7, 28), "1.0", "2.0"),
                (date(2026, 7, 29), "2.0", "1.0"),
                (date(2026, 7, 30), "3.0", "4.0"),
            ):
                provider.register_bars(symbol, "H4", [{
                    "broker_dt": datetime.combine(session_date, datetime.min.time()).replace(hour=20),
                    "open": float(opening),
                    "high": max(float(opening), float(closing)),
                    "low": min(float(opening), float(closing)),
                    "close": float(closing),
                    "open_exact": opening,
                    "close_exact": closing,
                    "is_complete": True,
                }])

        first = build_d_direction_snapshot_for_date(date(2026, 7, 29), provider)
        second = build_d_direction_snapshot_for_date(date(2026, 7, 30), provider)
        third = build_d_direction_snapshot_for_date(date(2026, 7, 31), provider)
        self.assertEqual(first["symbols"]["GBPUSD"]["session_date"], "2026-07-28")
        self.assertEqual(second["symbols"]["GBPUSD"]["session_date"], "2026-07-29")
        self.assertEqual(third["symbols"]["GBPUSD"]["session_date"], "2026-07-30")
        self.assertIsNot(first["symbols"], second["symbols"])


if __name__ == "__main__":
    unittest.main()
