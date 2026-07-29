"""Unit test suite for XAUUSD entry ready alert detection, deduplication, and retry queue."""
from datetime import datetime, timedelta
from unittest.mock import patch
import unittest

import mt5_signal_bot


class XauEntryAlertTests(unittest.TestCase):
    def setUp(self) -> None:
        mt5_signal_bot.entry_alerts_sent.clear()
        mt5_signal_bot.entry_alerts_pending.clear()

    def test_fingerprint_generation(self) -> None:
        fp = mt5_signal_bot.build_xau_entry_alert_fingerprint("2026-07-29", 7, 63, "BUY", "08:25")
        self.assertEqual(fp, "2026-07-29|7|63|BUY|08:25")

    def test_should_send_xau_entry_alert_detection(self) -> None:
        ready_record = {
          "source_date": "2026-07-29",
          "hour": 7,
          "logic_version": 63,
          "entry_state": "READY",
          "pair_entry_states": {"XAUUSD": "READY"},
          "pair_dirs": {"XAUUSD": "BUY", "GBPAUD": "BUY"},
          "pair_entry_times": {"XAUUSD": "08:25"},
        }
        self.assertTrue(mt5_signal_bot.should_send_xau_entry_alert(ready_record, set()))

        # Deduplication: If fingerprint is already in sent set, returns False
        fp = "2026-07-29|7|63|BUY|08:25"
        self.assertFalse(mt5_signal_bot.should_send_xau_entry_alert(ready_record, {fp}))

        # Non-READY state returns False
        pending_record = dict(ready_record, entry_state="PENDING_FOLLOWUP")
        self.assertFalse(mt5_signal_bot.should_send_xau_entry_alert(pending_record, set()))

    def test_send_alert_success_persists_fingerprint(self) -> None:
        record = {
          "source_date": "2026-07-29",
          "hour": 7,
          "logic_version": 63,
          "entry_state": "READY",
          "pair_entry_states": {"XAUUSD": "READY"},
          "pair_dirs": {"XAUUSD": "BUY", "GBPAUD": "BUY", "GBPUSD": "BUY"},
          "pair_entry_times": {"XAUUSD": "08:25", "GBPUSD": "09:00", "GBPAUD": "09:00"},
        }
        fp = "2026-07-29|7|63|BUY|08:25"
        broker_dt = datetime(2026, 7, 29, 7, 30)

        with patch.object(mt5_signal_bot, "send_telegram", return_value=True):
            res = mt5_signal_bot.send_xau_entry_ready_alert(record, broker_dt=broker_dt)

        self.assertTrue(res)
        self.assertIn(fp, mt5_signal_bot.entry_alerts_sent)
        self.assertNotIn(fp, mt5_signal_bot.entry_alerts_pending)

    def test_send_alert_failure_queues_pending_retry(self) -> None:
        record = {
          "source_date": "2026-07-29",
          "hour": 7,
          "logic_version": 63,
          "entry_state": "READY",
          "pair_entry_states": {"XAUUSD": "READY"},
          "pair_dirs": {"XAUUSD": "BUY", "GBPAUD": "BUY", "GBPUSD": "BUY"},
          "pair_entry_times": {"XAUUSD": "08:25", "GBPUSD": "09:00", "GBPAUD": "09:00"},
        }
        fp = "2026-07-29|7|63|BUY|08:25"
        broker_dt = datetime(2026, 7, 29, 7, 30)

        with patch.object(mt5_signal_bot, "send_telegram", return_value=False):
            res = mt5_signal_bot.send_xau_entry_ready_alert(record, broker_dt=broker_dt)

        self.assertFalse(res)
        self.assertNotIn(fp, mt5_signal_bot.entry_alerts_sent)
        self.assertIn(fp, mt5_signal_bot.entry_alerts_pending)

    def test_expired_entry_alert_is_not_sent(self) -> None:
        record = {
          "source_date": "2026-07-29",
          "hour": 7,
          "logic_version": 63,
          "entry_state": "READY",
          "pair_entry_states": {"XAUUSD": "READY"},
          "pair_dirs": {"XAUUSD": "BUY", "GBPAUD": "BUY", "GBPUSD": "BUY"},
          "pair_entry_times": {"XAUUSD": "08:25", "GBPUSD": "09:00", "GBPAUD": "09:00"},
        }
        # Broker time is 08:35 (10 minutes past entry 08:25 > 5 min grace limit)
        broker_dt_past_grace = datetime(2026, 7, 29, 8, 35)

        with patch.object(mt5_signal_bot, "send_telegram", return_value=True) as mock_send:
            res = mt5_signal_bot.send_xau_entry_ready_alert(record, broker_dt=broker_dt_past_grace)

        self.assertFalse(res)
        mock_send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
