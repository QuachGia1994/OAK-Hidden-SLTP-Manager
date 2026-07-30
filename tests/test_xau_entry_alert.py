"""XAUUSD v78 entry alert detection, deduplication, and retry queue."""

from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


def _ready_record():
    return {
        "source_date": "2026-07-29",
        "hour": 7,
        "logic_version": 78,
        "broker_utc_offset": 3,
        "entry_state": "READY",
        "pair_entry_states": {symbol: "READY" for symbol in mt5_signal_bot.SIGNAL_PAIRS},
        "pair_dirs": {
            "XAUUSD": "SELL",
            "GBPUSD": "SELL",
            "GBPAUD": "BUY",
            "GBPJPY": "WAIT",
            "GBPCAD": "WAIT",
        },
        "pair_entry_times": {
            "XAUUSD": "07:49",
            "GBPUSD": "08:00",
            "GBPAUD": "08:00",
            "GBPJPY": None,
            "GBPCAD": None,
        },
    }


class XauEntryAlertTests(unittest.TestCase):
    def setUp(self) -> None:
        mt5_signal_bot.entry_alerts_sent.clear()
        mt5_signal_bot.entry_alerts_pending.clear()

    def test_fingerprint_uses_version_date_hour_symbol_and_entry(self) -> None:
        fingerprint = mt5_signal_bot.build_xau_entry_alert_fingerprint(
            "2026-07-29", 7, 73, "XAUUSD", "07:49"
        )
        self.assertEqual(fingerprint, "73|2026-07-29|7|XAUUSD|07:49")

    def test_detection_and_deduplication(self) -> None:
        record = _ready_record()
        fingerprint = "78|2026-07-29|7|XAUUSD|07:49"
        self.assertTrue(mt5_signal_bot.should_send_xau_entry_alert(record, set()))
        self.assertFalse(mt5_signal_bot.should_send_xau_entry_alert(record, {fingerprint}))
        self.assertFalse(
            mt5_signal_bot.should_send_xau_entry_alert(
                {**record, "entry_state": "WAIT"}, set()
            )
        )

    def test_success_persists_fingerprint(self) -> None:
        fingerprint = "78|2026-07-29|7|XAUUSD|07:49"
        with (
            patch.object(mt5_signal_bot, "send_telegram", return_value=True),
            patch.object(mt5_signal_bot, "_save_state") as save_state,
        ):
            self.assertTrue(
                mt5_signal_bot.send_xau_entry_ready_alert(
                    _ready_record(), broker_dt=datetime(2026, 7, 29, 7, 50)
                )
            )

        self.assertIn(fingerprint, mt5_signal_bot.entry_alerts_sent)
        save_state.assert_called_once()


if __name__ == "__main__":
    unittest.main()
