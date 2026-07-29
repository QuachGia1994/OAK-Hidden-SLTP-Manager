"""Calendar helpers remain informational; they no longer deactivate direct slots."""
from datetime import datetime
import unittest

import mt4_mt5_server
import mt5_signal_bot


class LastFridayHelperTests(unittest.TestCase):
    def test_2026_last_fridays(self) -> None:
        expected = {(1, 30), (2, 27), (3, 27), (4, 24), (7, 31), (12, 25)}
        for month, day in expected:
            with self.subTest(month=month):
                self.assertEqual(mt5_signal_bot._last_friday_of_month(2026, month), day)


class RestrictedPeriodBoundaryTests(unittest.TestCase):
    def test_july_august_2026_boundary_helper(self) -> None:
        for day in range(28, 32):
            with self.subTest(day=f"2026-07-{day:02d}"):
                self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 7, day)))
        for day in range(1, 11):
            with self.subTest(day=f"2026-08-{day:02d}"):
                self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 8, day)))
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 7, 27)))
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 8, 11)))

    def test_december_january_boundary_helper(self) -> None:
        for day in range(22, 32):
            with self.subTest(day=f"2026-12-{day:02d}"):
                self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 12, day)))
        for day in range(1, 5):
            with self.subTest(day=f"2027-01-{day:02d}"):
                self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2027, 1, day)))
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 12, 21)))
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2027, 1, 5)))


class DeactivatedSlotTests(unittest.TestCase):
    def test_restricted_period_never_deactivates_a_direct_slot(self) -> None:
        dates = (datetime(2026, 7, 28), datetime(2026, 8, 6), datetime(2026, 8, 10))
        for broker_dt in dates:
            for hour in (6, 9, 12, 14, 16):
                with self.subTest(day=broker_dt.date(), hour=hour):
                    self.assertFalse(mt5_signal_bot.is_deactivated_signal_slot(broker_dt, hour))

    def test_only_early_reference_slots_are_deactivated(self) -> None:
        monday = datetime(2026, 7, 20)
        self.assertNotIn(4, mt5_signal_bot.ACTIVE_HOURS)
        self.assertFalse(mt5_signal_bot.is_deactivated_signal_slot(monday, 3))
        self.assertTrue(mt5_signal_bot.is_deactivated_signal_slot(datetime(2026, 7, 23), 3))


class Mt4ServerDeactivatedSlotTests(unittest.TestCase):
    def test_server_matches_signal_bot_direct_slot_deactivation_rules(self) -> None:
        dates = (datetime(2026, 7, 28), datetime(2026, 8, 6), datetime(2026, 8, 10))
        for broker_dt in dates:
            for hour in (6, 9, 12, 14, 16):
                with self.subTest(day=broker_dt.date(), hour=hour):
                    self.assertFalse(mt4_mt5_server.is_deactivated_slot(broker_dt, hour))

        self.assertTrue(mt4_mt5_server.is_deactivated_slot(datetime(2026, 7, 23), 3))


class NoneEdgeCaseTests(unittest.TestCase):
    def test_none_is_not_restricted_or_deactivated(self) -> None:
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(None))
        self.assertFalse(mt4_mt5_server._is_in_restricted_calendar_period(None))
        self.assertFalse(mt5_signal_bot.is_deactivated_signal_slot(None, 12))
        self.assertFalse(mt4_mt5_server.is_deactivated_slot(None, 12))


if __name__ == "__main__":
    unittest.main()
