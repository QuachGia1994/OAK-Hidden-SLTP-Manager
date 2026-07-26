"""Special Thu/Fri pairs and their signal-side effects."""
from datetime import datetime, timedelta
from unittest.mock import patch
import unittest

import mt5_signal_bot


class SpecialSignalDayTests(unittest.TestCase):
    def test_remaining_2026_calendar(self) -> None:
        expected_days = {
            "2026-07-30", "2026-07-31",
            "2026-08-06", "2026-08-07", "2026-08-27", "2026-08-28",
            "2026-09-03", "2026-09-04", "2026-09-24", "2026-09-25",
            "2026-10-01", "2026-10-02", "2026-10-29", "2026-10-30",
            "2026-11-26", "2026-11-27",
            "2026-12-03", "2026-12-04", "2026-12-24", "2026-12-25",
        }
        cursor = datetime(2026, 7, 26)
        last_day = datetime(2026, 12, 31)
        actual_days = set()

        while cursor <= last_day:
            if mt5_signal_bot.is_special_day(cursor):
                actual_days.add(cursor.date().isoformat())
            cursor += timedelta(days=1)

        self.assertEqual(actual_days, expected_days)

    def test_cross_year_pair_is_explicitly_not_special(self) -> None:
        self.assertFalse(mt5_signal_bot.is_special_day(datetime(2026, 12, 31)))
        self.assertFalse(mt5_signal_bot.is_special_day(datetime(2027, 1, 1)))

    def test_non_pair_days_are_not_special(self) -> None:
        for day in ("2026-07-23", "2026-07-24", "2026-08-13", "2026-12-17"):
            with self.subTest(day=day):
                self.assertFalse(mt5_signal_bot.is_special_day(datetime.fromisoformat(day)))

    def test_post_special_monday(self) -> None:
        self.assertTrue(mt5_signal_bot.is_post_special_day(datetime(2026, 8, 10)))
        self.assertFalse(mt5_signal_bot.is_post_special_day(datetime(2026, 8, 17)))
        self.assertFalse(mt5_signal_bot.is_post_special_day(datetime(2027, 1, 4)))

    def test_late_slots_are_suppressed_on_pair_and_post_monday(self) -> None:
        for broker_dt in (
            datetime(2026, 8, 6, 12, 0),
            datetime(2026, 8, 7, 12, 0),
            datetime(2026, 8, 10, 12, 0),
        ):
            for hour in (12, 14, 16):
                with self.subTest(day=broker_dt.date(), hour=hour):
                    result = mt5_signal_bot.calculate_slot_signal(broker_dt, hour)
                    self.assertEqual(result["signal"], "WAIT")
                    self.assertTrue(result["suppressed"])

    def test_h6_and_h9_are_not_suppressed_by_special_gate(self) -> None:
        special_thursday = datetime(2026, 8, 6, 9, 0)
        for hour in (6, 9):
            with self.subTest(hour=hour), patch.object(
                mt5_signal_bot,
                "_lookup_h3_signal_today",
                return_value=None,
            ), patch.object(
                mt5_signal_bot,
                "evaluate_4_m30_classification_before_hour",
                return_value="SW",
            ):
                result = mt5_signal_bot.calculate_slot_signal(special_thursday, hour)
                self.assertFalse(result.get("suppressed", False))

    def test_every_thursday_h3_is_deactivated(self) -> None:
        special_thursday = datetime(2026, 8, 6, 3, 0)
        regular_thursday = datetime(2026, 7, 23, 3, 0)
        special_friday = datetime(2026, 8, 7, 3, 0)

        with patch.object(
            mt5_signal_bot,
            "_lookup_historical_t2_signal",
            return_value="BUY",
        ), patch.object(
            mt5_signal_bot,
            "evaluate_3_m30_classification_for_h3",
            return_value="SW",
        ):
            thursday_result = mt5_signal_bot.calculate_slot_signal(special_thursday, 3)
            regular_thursday_result = mt5_signal_bot.calculate_slot_signal(regular_thursday, 3)
        with patch.object(
            mt5_signal_bot,
            "_lookup_h5_signal_yesterday",
            return_value="BUY",
        ), patch.object(
            mt5_signal_bot,
            "evaluate_3_m30_classification_for_h3",
            return_value="SW",
        ):
            friday_result = mt5_signal_bot.calculate_slot_signal(special_friday, 3)

        self.assertTrue(thursday_result["deactivated"])
        self.assertTrue(regular_thursday_result["deactivated"])
        self.assertEqual(friday_result["signal"], "SELL")
        self.assertFalse(friday_result.get("deactivated", False))

    def test_h4_and_h5_are_deactivated_every_weekday(self) -> None:
        monday = datetime(2026, 7, 20, 4, 45)

        for weekday in range(5):
            broker_dt = monday + timedelta(days=weekday)
            for hour in (4, 5):
                with self.subTest(weekday=weekday, hour=hour):
                    self.assertTrue(
                        mt5_signal_bot.is_deactivated_signal_slot(broker_dt, hour)
                    )

        self.assertFalse(mt5_signal_bot.is_deactivated_signal_slot(monday, 3))


if __name__ == "__main__":
    unittest.main()
