"""XAUUSD v72 entry alert detection, deduplication, and retry queue."""

from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


def _ready_record():
    return {
        "source_date": "2026-07-29",
        "hour": 7,
        "logic_version": 72,
        "broker_utc_offset": 3,
        "entry_state": "READY",
        "pair_entry_states": {symbol: "READY" for symbol in mt5_signal_bot.SIGNAL_PAIRS},
        "pair_dirs": {
            "XAUUSD": "SELL",
            "GBPUSD": "SELL",
            "GBPAUD": "BUY",
            "GBPJPY": "BUY",
            "GBPCAD": "SELL",
        },
        "pair_entry_times": {
            "XAUUSD": "07:49",
            "GBPUSD": "07:11",
            "GBPAUD": "07:49",
            "GBPJPY": "08:25",
            "GBPCAD": "07:49",
        },
    }


class XauEntryAlertTests(unittest.TestCase):
    def setUp(self) -> None:
        mt5_signal_bot.entry_alerts_sent.clear()
        mt5_signal_bot.entry_alerts_pending.clear()

    def test_fingerprint_uses_version_date_hour_symbol_and_entry(self) -> None:
        fingerprint = mt5_signal_bot.build_xau_entry_alert_fingerprint(
            "2026-07-29", 7, 72, "XAUUSD", "07:49"
        )
        self.assertEqual(fingerprint, "72|2026-07-29|7|XAUUSD|07:49")

    def test_detection_and_deduplication(self) -> None:
        record = _ready_record()
        fingerprint = "72|2026-07-29|7|XAUUSD|07:49"
        self.assertTrue(mt5_signal_bot.should_send_xau_entry_alert(record, set()))
        self.assertFalse(mt5_signal_bot.should_send_xau_entry_alert(record, {fingerprint}))
        self.assertFalse(
            mt5_signal_bot.should_send_xau_entry_alert(
                {**record, "entry_state": "WAIT"}, set()
            )
        )

    def test_success_persists_fingerprint(self) -> None:
        fingerprint = "72|2026-07-29|7|XAUUSD|07:49"
        with (
            patch.object(mt5_signal_bot, "send_telegram", return_value=True),
            patch.object(mt5_signal_bot, "_save_state"),
        ):
            sent = mt5_signal_bot.send_xau_entry_ready_alert(
                _ready_record(), broker_dt=datetime(2026, 7, 29, 7, 30)
            )
        self.assertTrue(sent)
        self.assertIn(fingerprint, mt5_signal_bot.entry_alerts_sent)
        self.assertNotIn(fingerprint, mt5_signal_bot.entry_alerts_pending)

    def test_failure_is_queued_for_retry(self) -> None:
        fingerprint = "72|2026-07-29|7|XAUUSD|07:49"
        with (
            patch.object(mt5_signal_bot, "send_telegram", return_value=False),
            patch.object(mt5_signal_bot, "_save_state"),
        ):
            sent = mt5_signal_bot.send_xau_entry_ready_alert(
                _ready_record(), broker_dt=datetime(2026, 7, 29, 7, 30)
            )
        self.assertFalse(sent)
        self.assertIn(fingerprint, mt5_signal_bot.entry_alerts_pending)

    def test_expired_entry_is_not_sent(self) -> None:
        with patch.object(mt5_signal_bot, "send_telegram") as send:
            result = mt5_signal_bot.send_xau_entry_ready_alert(
                _ready_record(), broker_dt=datetime(2026, 7, 29, 8)
            )
        self.assertFalse(result)
        send.assert_not_called()


if __name__ == "__main__":
    unittest.main()
