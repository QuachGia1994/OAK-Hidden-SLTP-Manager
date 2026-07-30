"""Canonical v72 signal record and Telegram payload fields."""

from datetime import datetime, timedelta, timezone
import json
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


class _UnresolvedBrokerClock:
    def utc_offset_for_date(self, _broker_date):
        raise mt5_signal_bot.BrokerClockError("offset unavailable")


class SignalRecordContractTests(unittest.TestCase):
    def test_h3_record_keeps_logical_slot_and_all_pair_entries(self) -> None:
        broker_dt = datetime(2026, 8, 6, 3)
        captured = []
        pair_dirs = {
            "XAUUSD": "BUY",
            "GBPUSD": "SELL",
            "GBPAUD": "BUY",
            "GBPJPY": "BUY",
            "GBPCAD": "SELL",
        }
        pair_entries = {
            "XAUUSD": "03:49",
            "GBPUSD": "04:00",
            "GBPAUD": "04:00",
            "GBPJPY": "04:00",
            "GBPCAD": "04:00",
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
        self.assertEqual(record["logic_version"], 72)
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

    def test_ready_telegram_lists_pair_specific_entries_without_groups(self) -> None:
        record = {
            "source_date": "2026-07-30",
            "hour": 7,
            "logic_version": 72,
            "broker_utc_offset": 3,
            "pair_dirs": {
                "GBPUSD": "SELL",
                "GBPAUD": "BUY",
                "GBPJPY": "SELL",
                "GBPCAD": "BUY",
                "XAUUSD": "BUY",
            },
            "pair_entry_times": {
                "GBPUSD": "08:00",
                "GBPAUD": "08:00",
                "GBPJPY": "08:00",
                "GBPCAD": "08:00",
                "XAUUSD": "07:49",
            },
        }
        message = mt5_signal_bot.build_entry_ready_telegram_message(record)
        self.assertIn("GBPUSD:", message)
        self.assertIn("Entry 08:00 Broker", message)
        self.assertIn("GBPJPY:", message)
        self.assertIn("Entry 08:00 Broker", message)
        self.assertIn("XAU direction: SAME AS GBPAUD (BUY)", message)
        self.assertNotIn("L1", message)
        self.assertNotIn("SW", message)
        self.assertNotIn("BT", message)

    def test_telegram_does_not_guess_local_time_without_broker_offset(self) -> None:
        record = {
            "source_date": "2026-07-30",
            "hour": 7,
            "pair_dirs": {symbol: "BUY" for symbol in mt5_signal_bot.SIGNAL_PAIRS},
            "pair_entry_times": {symbol: "07:49" for symbol in mt5_signal_bot.SIGNAL_PAIRS},
        }

        message = mt5_signal_bot.build_entry_ready_telegram_message(record)

        self.assertNotIn("GMT", message)
        self.assertIn("Entry 07:49 Broker", message)

    def test_state_persists_obligations_without_guessing_clock_metadata(self) -> None:
        with TemporaryDirectory() as directory:
            state_file = Path(directory) / "state.json"
            with (
                patch.object(mt5_signal_bot, "_STATE_FILE", str(state_file)),
                patch.object(mt5_signal_bot, "BROKER_CLOCK", _UnresolvedBrokerClock()),
            ):
                saved = mt5_signal_bot._save_state(
                    {(datetime(2026, 7, 30).date(), 7)},
                    broker_dt=datetime(2026, 7, 30, 7),
                )

            self.assertTrue(saved)
            state = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertIsNone(state["broker_utc_offset"])
            self.assertEqual(state["broker_time"], "")
            self.assertEqual(state["broker_observed_at_utc"], "")

    def test_state_save_fails_closed_without_any_broker_clock(self) -> None:
        with TemporaryDirectory() as directory:
            state_file = Path(directory) / "state.json"
            with (
                patch.object(mt5_signal_bot, "_STATE_FILE", str(state_file)),
                patch.object(
                    mt5_signal_bot,
                    "get_broker_time",
                    side_effect=mt5_signal_bot.BrokerClockError("clock unavailable"),
                ),
            ):
                saved = mt5_signal_bot._save_state(set())

            self.assertFalse(saved)
            self.assertFalse(state_file.exists())

    def test_active_slots_exclude_h4(self) -> None:
        self.assertEqual(mt5_signal_bot.ACTIVE_HOURS, frozenset({3, 7, 9, 12, 14, 16}))


if __name__ == "__main__":
    unittest.main()
