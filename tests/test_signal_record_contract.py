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
            patch.object(mt5_signal_bot, "_write_signals_log_atomic", side_effect=captured.append),
            patch.object(mt5_signal_bot.os.path, "exists", return_value=False),
        ):
            mt5_signal_bot.log_signal(
                3,
                broker_dt,
                "BUY",
                "03:11",
                {"XAUUSD": "BUY"},
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
        self.assertEqual(record["logic_version"], mt5_signal_bot.SIGNAL_LOGIC_VERSION)
        self.assertTrue(record["deactivated"])
        self.assertNotIn("is_priority", record)

    def test_h4_grouped_record_is_forced_deactivated(self) -> None:
        broker_dt = datetime(2026, 8, 4, 4, 0)
        captured = []

        with (
            patch.object(mt5_signal_bot, "BROKER_CLOCK", _FakeBrokerClock()),
            patch.object(mt5_signal_bot, "get_current_prices", return_value={}),
            patch.object(mt5_signal_bot, "_write_signals_log_atomic", side_effect=captured.append),
            patch.object(mt5_signal_bot.os.path, "exists", return_value=False),
        ):
            mt5_signal_bot.log_signal(4, broker_dt, "BUY", "04:49", {"XAUUSD": "BUY"}, "")

        record = captured[0][0]
        self.assertEqual(record["signal_time"], "04:00")
        self.assertEqual(record["entry_time"], "04:49")
        self.assertTrue(record["deactivated"])

    def test_special_h9_record_uses_the_normal_0900_publication_clock(self) -> None:
        broker_dt = datetime(2026, 8, 6, 9, 0)
        captured = []

        with (
            patch.object(mt5_signal_bot, "BROKER_CLOCK", _FakeBrokerClock()),
            patch.object(mt5_signal_bot, "get_current_prices", return_value={}),
            patch.object(mt5_signal_bot, "_write_signals_log_atomic", side_effect=captured.append),
            patch.object(mt5_signal_bot.os.path, "exists", return_value=False),
        ):
            mt5_signal_bot.log_signal(
                9,
                broker_dt,
                "SELL",
                "09:49",
                {"XAUUSD": "SELL"},
                "",
            )

        record = captured[0][0]
        self.assertEqual(record["hour"], 9)
        self.assertEqual(record["signal_time"], "09:00")
        self.assertEqual(record["entry_time"], "09:49")

    def test_deactivated_telegram_is_warning_only(self) -> None:
        broker_dt = datetime(2026, 8, 6, 3, 0)
        signal_data = {
            "signal": "BUY",
            "report": "trade-style report must not be forwarded",
            "deactivated": True,
            "entry_time": "03:11",
            "pair_dirs": {"XAUUSD": "BUY"},
        }

        with patch.object(mt5_signal_bot, "send_telegram") as send:
            mt5_signal_bot.send_report(signal_data, 3, broker_dt)

        message = send.call_args.args[0]
        self.assertIn("deactivated", message)
        self.assertIn("Mốc entry tham chiếu: 03:11 Broker", message)
        self.assertNotIn(signal_data["report"], message)

    def test_actionable_telegram_uses_calculated_entry_time(self) -> None:
        broker_dt = datetime(2026, 8, 5, 3, 0)
        signal_data = {
            "signal": "BUY",
            "report": "GBP H1/M15 confirmed",
            "entry_time": "04:49",
        }

        with (
            patch.object(mt5_signal_bot, "get_pair_direction", return_value={"XAUUSD": "BUY"}),
            patch.object(mt5_signal_bot, "format_telegram_pair_block", return_value="XAUUSD: BUY"),
            patch.object(mt5_signal_bot, "send_telegram") as send,
        ):
            mt5_signal_bot.send_report(signal_data, 3, broker_dt)

        self.assertIn("Vào lệnh: 04:49 Broker", send.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
