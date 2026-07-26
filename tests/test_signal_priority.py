"""Priority matrix for H6/H9 and H12/H14."""
from datetime import datetime, timedelta
from unittest.mock import patch
import unittest

import mt5_signal_bot


class SignalPriorityTests(unittest.TestCase):
    def test_five_weekday_matrix_for_sw_and_bt(self) -> None:
        monday = datetime(2026, 7, 20, 12, 0)

        for weekday in range(5):
            broker_dt = monday + timedelta(days=weekday)
            for group in ("SW", "BT"):
                with self.subTest(weekday=weekday, group=group), patch.object(
                    mt5_signal_bot,
                    "evaluate_4_m30_classification_before_hour",
                    return_value=group,
                ):
                    self.assertEqual(mt5_signal_bot.is_priority_slot(broker_dt, 6), group == "SW")
                    self.assertEqual(mt5_signal_bot.is_priority_slot(broker_dt, 9), group == "BT")
                    h12_group = "BT" if weekday in (0, 4) else "SW"
                    h14_group = "SW" if weekday in (0, 4) else "BT"
                    self.assertEqual(
                        mt5_signal_bot.is_priority_slot(broker_dt, 12),
                        group == h12_group,
                    )
                    self.assertEqual(
                        mt5_signal_bot.is_priority_slot(broker_dt, 14),
                        group == h14_group,
                    )

    def test_h16_selection_uses_only_h6_priority_group(self) -> None:
        thursday = datetime(2026, 7, 23, 16, 0)

        with (
            patch.object(
                mt5_signal_bot,
                "evaluate_4_m30_classification_before_hour",
                return_value="SW",
            ) as classify,
            patch.object(mt5_signal_bot, "_lookup_signal_from_log", return_value="BUY"),
        ):
            mt5_signal_bot.calculate_slot_signal(thursday, 16)

        classify.assert_called_once_with(thursday, 6)


if __name__ == "__main__":
    unittest.main()
