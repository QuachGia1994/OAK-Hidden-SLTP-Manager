"""Publication and entry clocks for the active logical signal slots."""
from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


ACTIVE_SLOTS = (3, 4, 6, 9, 12, 14, 16)


class SignalCoreScheduleTests(unittest.TestCase):
    def test_regular_publication_matrix(self) -> None:
        regular_tuesday = datetime(2026, 7, 14, 12, 0)
        expected = {
            3: "03:00",
            4: "04:00",
            6: "06:00",
            9: "09:00",
            12: "12:00",
            14: "14:00",
            16: "16:00",
        }
        self.assertEqual(
            {hour: mt5_signal_bot.get_signal_time_for_slot(regular_tuesday, hour) for hour in expected},
            expected,
        )

    def test_h9_special_dates_keep_the_normal_clock(self) -> None:
        for broker_dt in (datetime(2026, 8, 6), datetime(2026, 8, 7)):
            with self.subTest(day=broker_dt.date()):
                self.assertEqual(mt5_signal_bot.get_signal_time_for_slot(broker_dt, 9), "09:00")

    def test_dynamic_entry_time_comes_from_gbp_h1_evaluation(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        for hour, entry_time in ((3, "03:11"), (4, "05:25"), (9, "09:49"), (16, "16:11")):
            with self.subTest(hour=hour), patch.object(
                mt5_signal_bot,
                "evaluate_gbp_h1_slot",
                return_value={"entry_time": entry_time},
            ):
                self.assertEqual(mt5_signal_bot.get_entry_time_for_slot(broker_dt, hour), entry_time)

    def test_incomplete_classification_has_no_dynamic_entry(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        with patch.object(mt5_signal_bot, "evaluate_gbp_h1_slot", return_value=None):
            for hour in ACTIVE_SLOTS:
                with self.subTest(hour=hour):
                    self.assertIsNone(mt5_signal_bot.get_entry_time_for_slot(broker_dt, hour))

    def test_retry_deadlines_follow_the_resolved_entry_window(self) -> None:
        regular_tuesday = datetime(2026, 7, 14, 12, 0)
        entries = {3: "04:49", 4: "05:25", 6: "06:49", 9: "09:11", 12: "13:25", 14: "14:49", 16: "16:11"}
        for hour, entry_time in entries.items():
            with self.subTest(hour=hour), patch.object(
                mt5_signal_bot,
                "evaluate_gbp_h1_slot",
                return_value={"entry_time": entry_time},
            ):
                self.assertEqual(
                    mt5_signal_bot.get_slot_retry_deadline(regular_tuesday, hour).strftime("%H:%M:%S"),
                    f"{entry_time}:00",
                )


if __name__ == "__main__":
    unittest.main()
