import os
import tempfile
import unittest
from datetime import datetime, date
from unittest.mock import patch, MagicMock
from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot
from mt5_signal_bot import (
    reconstruct_sent_slots,
    catchup_due_slots,
    sent_today,
    set_market_data_provider,
    MT4FeedProvider,
)
from repositories.mt4_feed_store import MT4FeedStore


class TestDueSlotCatchup(unittest.TestCase):

    def setUp(self):
        self._original_provider = mt5_signal_bot.MARKET_DATA_PROVIDER
        self._temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self._temp_db.close()
        self._feed_store = MT4FeedStore(db_path=self._temp_db.name)
        self._provider = MT4FeedProvider(feed_store=self._feed_store)
        set_market_data_provider(self._provider)
        sent_today.clear()

    def tearDown(self):
        try:
            mt5_signal_bot.clear_history_cache()
        finally:
            set_market_data_provider(self._original_provider)
            self._feed_store.close()
            if os.path.exists(self._temp_db.name):
                os.unlink(self._temp_db.name)
            sent_today.clear()

    def test_reconstruct_sent_slots_reads_only_persisted_records(self):
        sample_records = [
            {"date": "2026-07-31", "hour": 3, "signal": "BUY", "logic_version": 87, "record_revision": 2},
            {"date": "2026-07-31", "hour": 7, "signal": "SELL", "logic_version": 87, "record_revision": 2},
        ]
        res = reconstruct_sent_slots(date(2026, 7, 31), records=sample_records)
        self.assertIn((date(2026, 7, 31), 3), res)
        self.assertIn((date(2026, 7, 31), 7), res)
        self.assertNotIn((date(2026, 7, 31), 14), res)

    def test_pending_layer3_record_is_retried_after_restart(self):
        records = [{
            "date": "2026-07-31",
            "hour": 7,
            "signal": "BUY",
            "logic_version": 87,
            "record_revision": 1,
            "entry_state": "PENDING_LAYER3",
        }]
        self.assertNotIn((date(2026, 7, 31), 7), reconstruct_sent_slots(date(2026, 7, 31), records=records))

    @patch("mt5_signal_bot.store")
    @patch("mt5_signal_bot.ensure_d_direction_ready")
    @patch("mt5_signal_bot.evaluate_all_pairs_for_slot")
    @patch("mt5_signal_bot._persist_live_result")
    @patch("mt5_signal_bot._load_signals_log_records", return_value=[])
    def test_catchup_at_14_02_evaluates_h14_immediately(
        self, mock_log, mock_persist, mock_eval, mock_d_ready, mock_store
    ):
        mock_store.get_signals_by_date.return_value = [
            {"date": "2026-07-24", "hour": 3, "signal": "BUY", "logic_version": 87, "record_revision": 2, "entry_state": "READY"},
            {"date": "2026-07-24", "hour": 7, "signal": "WAIT", "logic_version": 87, "record_revision": 1, "entry_state": "READY"},
            {"date": "2026-07-24", "hour": 9, "signal": "WAIT", "logic_version": 87, "record_revision": 1, "entry_state": "READY"},
            {"date": "2026-07-24", "hour": 12, "signal": "WAIT", "logic_version": 87, "record_revision": 1, "entry_state": "READY"},
        ]
        mock_eval.return_value = {
            "date": "2026-07-24",
            "hour": 14,
            "signal": "BUY",
            "signal_state": "READY",
            "entry_state": "READY",
            "entry_time": "14:11",
            "hour_note": "H14 Friday",
        }

        broker_now = datetime(2026, 7, 24, 14, 2, 0)  # 14:02 Broker
        catchup_due_slots(broker_now)

        # H14 should have been evaluated and persisted
        mock_eval.assert_called()
        evaluated_hours = [call[0][1] for call in mock_eval.call_args_list]
        self.assertIn(14, evaluated_hours)
        self.assertIn((date(2026, 7, 24), 14), sent_today)


if __name__ == "__main__":
    unittest.main()
