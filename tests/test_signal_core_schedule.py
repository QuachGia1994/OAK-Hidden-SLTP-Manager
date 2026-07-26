"""Publication and entry clocks for every active logical signal slot."""
from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


class SignalCoreScheduleTests(unittest.TestCase):
    def test_regular_publication_matrix(self) -> None:
        regular_tuesday = datetime(2026, 7, 14, 12, 0)
        expected = {
            3: "03:00",
            4: "04:45",
            5: "05:45",
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

    def test_special_h9_publishes_at_0800(self) -> None:
        for broker_dt in (datetime(2026, 8, 6), datetime(2026, 8, 7)):
            with self.subTest(day=broker_dt.date()):
                self.assertEqual(mt5_signal_bot.get_signal_time_for_slot(broker_dt, 9), "08:00")
                self.assertEqual(mt5_signal_bot.get_entry_time_for_slot(broker_dt, 9), "08:30")

    def test_dynamic_entry_matrix(self) -> None:
        regular_tuesday = datetime(2026, 7, 14, 12, 0)
        fixed = {
            4: "04:45",
            5: "05:45",
            6: "06:11",
            9: "09:49",
            12: "12:11",
        }

        for hour, expected in fixed.items():
            with self.subTest(hour=hour):
                self.assertEqual(
                    mt5_signal_bot.get_entry_time_for_slot(regular_tuesday, hour),
                    expected,
                )

        with patch.object(mt5_signal_bot, "evaluate_3_m30_classification_for_h3", return_value="BT"):
            self.assertEqual(mt5_signal_bot.get_entry_time_for_slot(regular_tuesday, 3), "03:11")
        with patch.object(mt5_signal_bot, "evaluate_3_m30_classification_for_h3", return_value="SW"):
            self.assertEqual(mt5_signal_bot.get_entry_time_for_slot(regular_tuesday, 3), "03:49")
        with patch.object(mt5_signal_bot, "evaluate_4_m30_classification_before_hour", return_value="SW"):
            self.assertEqual(mt5_signal_bot.get_entry_time_for_slot(regular_tuesday, 14), "14:15")
            self.assertEqual(mt5_signal_bot.get_entry_time_for_slot(regular_tuesday, 16), "16:11")
        with patch.object(mt5_signal_bot, "evaluate_4_m30_classification_before_hour", return_value="BT"):
            self.assertEqual(mt5_signal_bot.get_entry_time_for_slot(regular_tuesday, 14), "14:49")
            self.assertEqual(mt5_signal_bot.get_entry_time_for_slot(regular_tuesday, 16), "16:49")

    def test_incomplete_classification_has_no_dynamic_entry(self) -> None:
        broker_dt = datetime(2026, 7, 14, 12, 0)
        with patch.object(mt5_signal_bot, "evaluate_3_m30_classification_for_h3", return_value=None):
            self.assertIsNone(mt5_signal_bot.get_entry_time_for_slot(broker_dt, 3))
        with patch.object(mt5_signal_bot, "evaluate_4_m30_classification_before_hour", return_value=None):
            self.assertIsNone(mt5_signal_bot.get_entry_time_for_slot(broker_dt, 14))
            self.assertIsNone(mt5_signal_bot.get_entry_time_for_slot(broker_dt, 16))

    def test_retry_deadlines_never_exceed_entry_window(self) -> None:
        regular_tuesday = datetime(2026, 7, 14, 12, 0)
        expected = {
            4: "04:45:59",
            5: "05:45:59",
            6: "06:11:00",
            9: "09:49:00",
            12: "12:11:00",
        }

        for hour, expected_clock in expected.items():
            with self.subTest(hour=hour):
                deadline = mt5_signal_bot.get_slot_retry_deadline(regular_tuesday, hour)
                self.assertEqual(deadline.strftime("%H:%M:%S"), expected_clock)

        with patch.object(mt5_signal_bot, "evaluate_3_m30_classification_for_h3", return_value="BT"):
            self.assertEqual(
                mt5_signal_bot.get_slot_retry_deadline(regular_tuesday, 3).strftime("%H:%M:%S"),
                "03:11:00",
            )
        with patch.object(mt5_signal_bot, "evaluate_3_m30_classification_for_h3", return_value="SW"):
            self.assertEqual(
                mt5_signal_bot.get_slot_retry_deadline(regular_tuesday, 3).strftime("%H:%M:%S"),
                "03:49:00",
            )
        with patch.object(mt5_signal_bot, "evaluate_4_m30_classification_before_hour", return_value="SW"):
            self.assertEqual(
                mt5_signal_bot.get_slot_retry_deadline(regular_tuesday, 14).strftime("%H:%M:%S"),
                "14:15:00",
            )
            self.assertEqual(
                mt5_signal_bot.get_slot_retry_deadline(regular_tuesday, 16).strftime("%H:%M:%S"),
                "16:11:00",
            )
        with patch.object(mt5_signal_bot, "evaluate_4_m30_classification_before_hour", return_value="BT"):
            self.assertEqual(
                mt5_signal_bot.get_slot_retry_deadline(regular_tuesday, 14).strftime("%H:%M:%S"),
                "14:49:00",
            )
            self.assertEqual(
                mt5_signal_bot.get_slot_retry_deadline(regular_tuesday, 16).strftime("%H:%M:%S"),
                "16:49:00",
            )


if __name__ == "__main__":
    unittest.main()
