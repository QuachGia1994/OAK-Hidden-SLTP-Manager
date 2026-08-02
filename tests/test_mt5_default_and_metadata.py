import unittest
import os
import tempfile
from datetime import date, datetime, timezone

from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot
from mt5_signal_bot import (
    D_SOURCE_SYMBOL,
    build_d_direction_snapshot_for_date,
    set_market_data_provider,
    MT4FeedProvider,
)
from repositories.mt4_feed_store import MT4FeedStore


class TestMT5DefaultAndMetadata(unittest.TestCase):
    """Default market-data provider is MT5 and rebuilt records carry metadata."""

    def tearDown(self):
        set_market_data_provider(mt5_signal_bot.MARKET_DATA_PROVIDER)

    def _build_provider(self):
        temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        temp_db.close()
        store = MT4FeedStore(db_path=temp_db.name)
        self.addCleanup(store.close)
        self.addCleanup(lambda: os.path.exists(temp_db.name) and os.unlink(temp_db.name))
        return MT4FeedProvider(feed_store=store), store

    def test_xauusd_direction_shares_gbpusd_d_source(self):
        provider, store = self._build_provider()
        store.save_heartbeat({
            "schema_version": 2,
            "source_id": "test-ea",
            "broker_time": "2026-07-30T14:00:00",
            "broker_utc_offset": 3,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        })
        for session_date, opening, closing in (
            (date(2026, 7, 28), "1.0", "2.0"),
            (date(2026, 7, 29), "2.0", "1.0"),
            (date(2026, 7, 30), "3.0", "4.0"),
        ):
            for symbol in ("XAUUSD", "GBPUSD"):
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

        self.assertEqual(D_SOURCE_SYMBOL["XAUUSD"], "GBPUSD")
        snapshot = build_d_direction_snapshot_for_date(date(2026, 7, 30), provider)
        xau = snapshot["symbols"]["XAUUSD"]
        gbp = snapshot["symbols"]["GBPUSD"]
        self.assertEqual(xau["session_date"], gbp["session_date"])
        self.assertEqual(xau["session_date"], "2026-07-29")
        self.assertIsNot(xau, gbp)

    def test_default_market_data_provider_is_mt5(self):
        default = mt5_signal_bot.MARKET_DATA_PROVIDER
        self.assertEqual(getattr(default, "name", ""), "MT5")


if __name__ == "__main__":
    unittest.main()