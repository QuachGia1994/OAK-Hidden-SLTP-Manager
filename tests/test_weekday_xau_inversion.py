"""Table-driven unit tests for XAUUSD weekday inversion matrix and v60 logic pipeline."""
from datetime import datetime
from unittest.mock import patch
import unittest

import mt5_signal_bot


class WeekdayXauInversionTests(unittest.TestCase):
    def test_xauusd_weekday_inversion_hours_truth_table(self) -> None:
        """Verify the XAUUSD weekday inversion matrix for each day of the week."""
        # Dates for 2026:
        # Mon: 2026-07-13 (weekday 0)
        # Tue: 2026-07-14 (weekday 1)
        # Wed: 2026-07-15 (weekday 2)
        # Thu: 2026-07-16 (weekday 3)
        # Fri: 2026-07-17 (weekday 4)
        dates = {
            0: (datetime(2026, 7, 13, 12, 0), {7, 14}),
            1: (datetime(2026, 7, 14, 12, 0), set()),
            2: (datetime(2026, 7, 15, 12, 0), {3, 7, 9, 12, 14, 16}),
            3: (datetime(2026, 7, 16, 12, 0), {7, 9}),
            4: (datetime(2026, 7, 17, 12, 0), {3, 12, 16}),
        }

        all_slots = (3, 4, 7, 9, 12, 14, 16)
        for weekday, (dt, expected_inverted_slots) in dates.items():
            self.assertEqual(dt.weekday(), weekday)
            for h in all_slots:
                with self.subTest(weekday=weekday, hour=h):
                    should_invert = mt5_signal_bot.should_invert_xauusd_for_weekday(dt, h)
                    if h == 4:
                        # Internal slot H4 is never weekday-inverted
                        self.assertFalse(should_invert)
                    else:
                        self.assertEqual(should_invert, h in expected_inverted_slots)

    def test_h4_is_never_weekday_inverted(self) -> None:
        for weekday_dt in (
            datetime(2026, 7, 13),  # Mon
            datetime(2026, 7, 14),  # Tue
            datetime(2026, 7, 15),  # Wed
            datetime(2026, 7, 16),  # Thu
            datetime(2026, 7, 17),  # Fri
        ):
            with self.subTest(day=weekday_dt.date()):
                self.assertFalse(mt5_signal_bot.should_invert_xauusd_for_weekday(weekday_dt, 4))

    def test_unconditional_h14_reversal_is_removed(self) -> None:
        """Verify H14 on Tuesday (weekday 1) is NOT inverted since Tue has no weekday inversion."""
        tuesday_dt = datetime(2026, 7, 14, 14, 0)
        with (
            patch.object(mt5_signal_bot, "_lookback_candle_direction", return_value="TANG"),
            patch.object(mt5_signal_bot, "apply_offset15_filter", return_value={
                "offset15_signal": "BUY",
                "relation": "SAME",
                "action": "REVERSE_PROVISIONAL",
                "final_signal": "SELL",
            }),
        ):
            res = mt5_signal_bot.evaluate_symbol_m15_for_slot(tuesday_dt, 14, "XAUUSD")
            self.assertIsNotNone(res)
            self.assertEqual(res["direction"], "SELL")
            self.assertFalse(res["weekday_inversion_applied"])

    def test_wednesday_all_slots_invert_xauusd(self) -> None:
        wednesday_dt = datetime(2026, 7, 15, 12, 0)
        for h in (3, 7, 9, 12, 14, 16):
            with (
                self.subTest(hour=h),
                patch.object(mt5_signal_bot, "_lookback_candle_direction", return_value="TANG"),
                patch.object(mt5_signal_bot, "apply_offset15_filter", return_value={
                    "offset15_signal": "BUY",
                    "relation": "SAME",
                    "action": "REVERSE_PROVISIONAL",
                    "final_signal": "SELL",
                }),
            ):
                self.assertTrue(mt5_signal_bot.should_invert_xauusd_for_weekday(wednesday_dt, h))
                res = mt5_signal_bot.evaluate_symbol_m15_for_slot(wednesday_dt, h, "XAUUSD")
                self.assertIsNotNone(res)
                # Active weekday inversion is disabled in v62
                self.assertFalse(res["weekday_inversion_applied"])
                self.assertIsNone(res["weekday_inversion_rule"])


if __name__ == "__main__":
    unittest.main()
