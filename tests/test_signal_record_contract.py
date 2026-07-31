"""Canonical v76 signal record and Telegram payload fields."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

import mt5_signal_bot


class _FakeBrokerClock:
    timestamp_mode = "true_utc"

    def utc_from_broker_datetime(self, broker_dt):
        return broker_dt.replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc)

    def utc_offset_for_date(self, _broker_date):
        return 3


class SignalRecordContractTests(unittest.TestCase):
    def test_h3_record_keeps_logical_slot_and_all_pair_entries(self) -> None:
        broker_dt = datetime(2026, 8, 6, 3)
        captured = []
        pair_dirs = {
            "XAUUSD": "BUY",
            "GBPUSD": "SELL",
            "GBPAUD": "BUY",
            "GBPJPY": "WAIT",
            "GBPCAD": "WAIT",
        }
        pair_entries = {
            "XAUUSD": "03:49",
            "GBPUSD": "04:00",
            "GBPAUD": "04:00",
            "GBPJPY": None,
            "GBPCAD": None,
        }
        with (
            patch.object(mt5_signal_bot, "BROKER_CLOCK", _FakeBrokerClock()),
            patch.object(mt5_signal_bot, "get_current_prices", return_value={}),
            patch.object(mt5_signal_bot, "_write_signals_log_atomic", side_effect=captured.append),
            patch.object(mt5_signal_bot.os.path, "exists", return_value=False),
        ):
            mt5_signal_bot.log_signal(
                3,
                broker_dt,
                "BUY",
                "03:49",
                pair_dirs,
                "",
                extra_fields={"pair_entry_times": pair_entries},
            )

        record = captured[0][0]
        self.assertEqual(record["hour"], 3)
        self.assertEqual(record["signal_time"], "03:00")
        self.assertEqual(record["entry_time"], "03:49")
        self.assertEqual(record["pair_entry_times"], pair_entries)
        self.assertEqual(record["signal_at_utc"], "2026-08-06T00:00:00+00:00")
        self.assertEqual(record["broker_utc_offset"], 3)
        self.assertEqual(record["logic_version"], 83)
        self.assertFalse(record["deactivated"])

    def test_wait_record_never_invents_an_entry_time(self) -> None:
        captured = []
        with (
            patch.object(mt5_signal_bot, "BROKER_CLOCK", _FakeBrokerClock()),
            patch.object(mt5_signal_bot, "get_current_prices", return_value={}),
            patch.object(mt5_signal_bot, "_write_signals_log_atomic", side_effect=captured.append),
            patch.object(mt5_signal_bot.os.path, "exists", return_value=False),
            patch.object(mt5_signal_bot, "get_entry_time_for_slot") as fallback,
        ):
            mt5_signal_bot.log_signal(
                7,
                datetime(2026, 7, 30, 7),
                "WAIT",
                None,
                {symbol: "WAIT" for symbol in mt5_signal_bot.SIGNAL_PAIRS},
                "",
            )

        self.assertIsNone(captured[0][0]["entry_time"])
        fallback.assert_not_called()

if __name__ == "__main__":
    unittest.main()
