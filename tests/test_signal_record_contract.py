"""Canonical signal record fields shared by API and dashboard."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import unittest

import mt5_signal_bot


class _FakeBrokerClock:
    def utc_from_broker_datetime(self, broker_dt):
        return broker_dt.replace(tzinfo=timezone(timedelta(hours=3))).astimezone(timezone.utc)

    def utc_offset_for_date(self, _broker_date):
        return 3


class SignalRecordContractTests(unittest.TestCase):
    def test_h3_record_keeps_logical_slot_and_broker_clock_metadata(self) -> None:
        broker_dt = datetime(2026, 8, 6, 3, 0)
        captured = []

        with (
            patch.object(mt5_signal_bot, "BROKER_CLOCK", _FakeBrokerClock()),
            patch.object(mt5_signal_bot, "get_current_prices", return_value={}),
            patch.object(mt5_signal_bot, "is_priority_slot", return_value=False),
            patch.object(mt5_signal_bot, "_write_signals_log_atomic", side_effect=captured.append),
            patch.object(mt5_signal_bot.os.path, "exists", return_value=False),
        ):
            mt5_signal_bot.log_signal(
                3,
                broker_dt,
                "BUY",
                "03:11",
                {"XAUUSD": "BUY", "GBPAUD": "SELL"},
                "",
                deactivated=True,
            )

        record = captured[0][0]
        self.assertEqual(record["hour"], 3)
        self.assertEqual(record["signal_time"], "03:00")
        self.assertEqual(record["entry_time"], "03:11")
        self.assertEqual(record["signal_at_utc"], "2026-08-06T00:00:00+00:00")
        self.assertEqual(record["broker_utc_offset"], 3)
        self.assertTrue(record["broker_clock_verified"])
        self.assertEqual(record["logic_version"], 41)
        self.assertTrue(record["deactivated"])

    def test_h4_record_is_forced_deactivated_for_dependency_only_use(self) -> None:
        broker_dt = datetime(2026, 8, 4, 4, 45)
        captured = []

        with (
            patch.object(mt5_signal_bot, "BROKER_CLOCK", _FakeBrokerClock()),
            patch.object(mt5_signal_bot, "get_current_prices", return_value={}),
            patch.object(mt5_signal_bot, "is_priority_slot", return_value=False),
            patch.object(mt5_signal_bot, "_write_signals_log_atomic", side_effect=captured.append),
            patch.object(mt5_signal_bot.os.path, "exists", return_value=False),
        ):
            mt5_signal_bot.log_signal(4, broker_dt, "BUY", "04:45", {"XAUUSD": "BUY"}, "")

        self.assertTrue(captured[0][0]["deactivated"])

    def test_special_h9_record_keeps_logical_hour_despite_0800_publication(self) -> None:
        broker_dt = datetime(2026, 8, 6, 8, 0)
        captured = []

        with (
            patch.object(mt5_signal_bot, "BROKER_CLOCK", _FakeBrokerClock()),
            patch.object(mt5_signal_bot, "get_current_prices", return_value={}),
            patch.object(mt5_signal_bot, "is_priority_slot", return_value=False),
            patch.object(mt5_signal_bot, "_write_signals_log_atomic", side_effect=captured.append),
            patch.object(mt5_signal_bot.os.path, "exists", return_value=False),
        ):
            mt5_signal_bot.log_signal(
                9,
                broker_dt,
                "SELL",
                "08:30",
                {"XAUUSD": "SELL", "GBPUSD": "BUY", "GBPAUD": "BUY"},
                "",
            )

        record = captured[0][0]
        self.assertEqual(record["hour"], 9)
        self.assertEqual(record["signal_time"], "08:00")
        self.assertEqual(record["entry_time"], "08:30")

    def test_deactivated_telegram_is_warning_only(self) -> None:
        broker_dt = datetime(2026, 8, 6, 3, 0)
        signal_data = {
            "signal": "BUY",
            "report": "trade-style report must not be forwarded",
            "deactivated": True,
            "skip_xau_m30": True,
            "pair_dirs": {"XAUUSD": "BUY", "GBPAUD": "SELL"},
        }

        with (
            patch.object(mt5_signal_bot, "evaluate_3_m30_classification_for_h3", return_value="BT"),
            patch.object(mt5_signal_bot, "send_telegram") as send,
        ):
            mt5_signal_bot.send_report(signal_data, 3, broker_dt)

        message = send.call_args.args[0]
        self.assertIn("deactivated", message)
        self.assertNotIn(signal_data["report"], message)


if __name__ == "__main__":
    unittest.main()
