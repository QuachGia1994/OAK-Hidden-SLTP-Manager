import os
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot
from mt5_signal_bot import evaluate_all_pairs_for_slot, MT4FeedProvider, set_market_data_provider
from repositories.mt4_feed_store import MT4FeedStore

class TestSignalEngineMT4Only(unittest.TestCase):
    def setUp(self):
        self._original_provider = mt5_signal_bot.MARKET_DATA_PROVIDER
        self._temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self._temp_db.close()
        self._feed_store = MT4FeedStore(db_path=self._temp_db.name)
        self.provider = MT4FeedProvider(feed_store=self._feed_store)
        set_market_data_provider(self.provider)
        mt5_signal_bot.clear_history_cache()

    def tearDown(self):
        try:
            mt5_signal_bot.clear_history_cache()
        finally:
            set_market_data_provider(self._original_provider)
            self._feed_store.close()
            if os.path.exists(self._temp_db.name):
                os.unlink(self._temp_db.name)

    @patch("mt5_signal_bot.BROKER_CLOCK")
    def test_signal_evaluation_does_not_call_mt5_copy_rates(self, mock_clock):
        mock_clock.utc_offset_for_date.return_value = 3
        mock_clock.mt5_timestamp_from_broker_datetime.side_effect = lambda dt: int((dt.replace(tzinfo=timezone.utc)).timestamp())

        b_dt = datetime(2026, 7, 30, 7, 0, tzinfo=timezone.utc)
        self.provider.register_bars("GBPUSD", "16385", [{"broker_dt": b_dt, "time": int(b_dt.timestamp()), "open": 1.34, "high": 1.35, "low": 1.33, "close": 1.345}])

        with patch("mt5_signal_bot.mt5") as mock_mt5:
            mock_mt5.copy_rates_from.side_effect = AssertionError("MT5 copy_rates_from should not be called!")
            mock_mt5.copy_rates_range.side_effect = AssertionError("MT5 copy_rates_range should not be called!")
            mock_mt5.copy_rates_from_pos.side_effect = AssertionError("MT5 copy_rates_from_pos should not be called!")

            slot_dt = datetime(2026, 7, 30, 7, 0)
            res = evaluate_all_pairs_for_slot(slot_dt, 7)
            self.assertIsNotNone(res)

if __name__ == "__main__":
    unittest.main()
