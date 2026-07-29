"""Regression tests for signal-log consumers outside the signal bot."""
from pathlib import Path
import unittest

import mimo_bot
from domain import copy_trade_manager


CURRENT_RECORD = {
    "date": "2026-07-28",
    "hour": 9,
    "logic_version": 60,
    "signal_time": "09:00",
    "entry_time": "10:25",
    "pair_dirs": {"XAUUSD": "BUY", "GBPUSD": "SELL", "GBPAUD": "BUY"},
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
                self.assertIn("10:25 Broker", rendered)
                self.assertIn("XAUUSD:BUY", rendered)
                self.assertNotIn("GBPUSD", rendered)
                self.assertNotIn("GBPAUD", rendered)
                self.assertNotIn("H=09:45", rendered)

    def test_deactivated_record_is_presented_as_do_not_enter(self) -> None:
        payload = {**CURRENT_RECORD, "deactivated": True}

        for consumer in (mimo_bot, copy_trade_manager):
            with self.subTest(consumer=consumer.__name__):
                rendered = consumer._format_current_signal_row(9, payload)
                self.assertNotIn("vào ", rendered)
                self.assertIn("entry tham chiếu", rendered)

    def test_h4_and_thursday_h3_are_defensively_do_not_enter(self) -> None:
        h4 = {**CURRENT_RECORD, "hour": 4, "deactivated": False}
        thursday_h3 = {
            **CURRENT_RECORD,
            "date": "2026-07-30",
            "hour": 3,
            "deactivated": False,
        }
        tuesday_h3 = {
            **CURRENT_RECORD,
            "date": "2026-07-28",
            "hour": 3,
            "deactivated": False,
        }

        for consumer in (mimo_bot, copy_trade_manager):
            with self.subTest(consumer=consumer.__name__):
                # h4 and thursday_h3 should NOT contain actionable entry word
                self.assertNotIn("vào ", consumer._format_current_signal_row(4, h4))
                self.assertIn("entry tham chiếu", consumer._format_current_signal_row(4, h4))
                self.assertNotIn("vào ", consumer._format_current_signal_row(3, thursday_h3))
                self.assertIn("entry tham chiếu", consumer._format_current_signal_row(3, thursday_h3))
                # tuesday_h3 should still be rendered normally with actionable entry
                self.assertIn("vào ", consumer._format_current_signal_row(3, tuesday_h3))

    def test_copy_manager_reads_signal_state_from_repository_root(self) -> None:
        state_path, log_path = copy_trade_manager._signal_state_paths()
        project_root = Path(copy_trade_manager.__file__).resolve().parents[1]

        self.assertEqual(Path(state_path), project_root / "bot_state.json")
        self.assertEqual(Path(log_path), project_root / "signals_log.json")


if __name__ == "__main__":
    unittest.main()
