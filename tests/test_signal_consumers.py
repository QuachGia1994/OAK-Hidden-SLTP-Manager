"""Regression tests for signal-log consumers outside the signal bot."""
from pathlib import Path
import unittest

import mimo_bot
from domain import copy_trade_manager


CURRENT_RECORD = {
    "date": "2026-07-28",
    "hour": 9,
    "logic_version": 87,
    "signal_time": "09:00",
    "entry_time": "09:49",
    "pair_dirs": {
        "XAUUSD": "BUY",
        "GBPUSD": "BUY",
        "GBPAUD": "SELL",
        "GBPJPY": "SELL",
        "GBPCAD": "SELL",
    },
    "pair_entry_times": {
        "XAUUSD": "09:49",
        "GBPUSD": "09:49",
        "GBPAUD": "09:49",
        "GBPJPY": "09:49",
        "GBPCAD": "09:49",
    },
}


class SignalConsumerContractTests(unittest.TestCase):
    def test_consumers_reject_stale_missing_version_and_inactive_slots(self) -> None:
        rows = [
            CURRENT_RECORD,
            {**CURRENT_RECORD, "hour": 12, "logic_version": 48},
            {key: value for key, value in CURRENT_RECORD.items() if key != "logic_version"},
            {**CURRENT_RECORD, "hour": 5},
            {**CURRENT_RECORD, "hour": 14, "pair_dirs": {"GBPUSD": "BUY"}},
            {**CURRENT_RECORD, "date": "not-a-date", "hour": 16},
        ]

        for consumer in (mimo_bot, copy_trade_manager):
            with self.subTest(consumer=consumer.__name__):
                selected_date, by_hour = consumer._select_current_signal_rows(rows)
                self.assertEqual(selected_date, "2026-07-28")
                self.assertEqual(list(by_hour), [9])

    def test_consumers_render_only_xau_and_use_record_clocks(self) -> None:
        for consumer in (mimo_bot, copy_trade_manager):
            with self.subTest(consumer=consumer.__name__):
                rendered = consumer._format_current_signal_row(9, CURRENT_RECORD)
                self.assertIn("09:00 Broker", rendered)
                self.assertIn("09:49 Broker", rendered)
                self.assertIn("XAUUSD:BUY", rendered)
                self.assertNotIn("GBPUSD", rendered)
                self.assertNotIn("GBPAUD", rendered)
                self.assertNotIn("H=09:45", rendered)

    def test_legacy_deactivated_flag_does_not_change_signal_presentation(self) -> None:
        deactivated_record = {**CURRENT_RECORD, "deactivated": True}
        for consumer in (mimo_bot, copy_trade_manager):
            with self.subTest(consumer=consumer.__name__):
                rendered = consumer._format_current_signal_row(9, deactivated_record)
                self.assertIn("vào 09:49 Broker", rendered)
                self.assertNotIn("KHÔNG VÀO LỆNH", rendered)


if __name__ == "__main__":
    unittest.main()
