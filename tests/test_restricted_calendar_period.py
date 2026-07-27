"""Restricted calendar period: Tue of week with last Fri of month → Mon after first Fri of next month."""
from datetime import datetime
import unittest

import mt5_signal_bot
import mt4_mt5_server


class LastFridayHelperTests(unittest.TestCase):
    def test_july_2026_last_friday_is_31(self):
        self.assertEqual(mt5_signal_bot._last_friday_of_month(2026, 7), 31)

    def test_february_2026_last_friday(self):
        # Feb 2026: Fridays = 6,13,20,27. Last = 27
        self.assertEqual(mt5_signal_bot._last_friday_of_month(2026, 2), 27)

    def test_march_2026_last_friday(self):
        # March 2026: Fridays = 6,13,20,27. Last = 27
        self.assertEqual(mt5_signal_bot._last_friday_of_month(2026, 3), 27)

    def test_january_2026_last_friday(self):
        # Jan 2026: Fridays = 2,9,16,23,30. Last = 30
        self.assertEqual(mt5_signal_bot._last_friday_of_month(2026, 1), 30)

    def test_december_2026_last_friday(self):
        # Dec 2026: starts Tuesday. Fridays = 4,11,18,25. Last = 25
        self.assertEqual(mt5_signal_bot._last_friday_of_month(2026, 12), 25)

    def test_april_2026_last_friday(self):
        # Apr 2026: starts Wednesday. Fri 1st = day 3. Fridays = 3,10,17,24. Last = 24
        self.assertEqual(mt5_signal_bot._last_friday_of_month(2026, 4), 24)


class RestrictedPeriodBoundaryTests(unittest.TestCase):
    """Test _is_in_restricted_calendar_period for July→August 2026 example."""

    def test_jul_28_is_in_restricted(self):
        # Last Fri of Jul = 31, Tue of that week = 28 → start
        self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 7, 28)))

    def test_aug_10_is_in_restricted(self):
        # Mon after first Fri of Aug = end
        self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 8, 10)))

    def test_jul_27_is_NOT_in_restricted(self):
        # Day before the Tuesday of last-Fri week
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 7, 27)))

    def test_aug_11_is_NOT_in_restricted(self):
        # Day after Mon after first Fri of Aug
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 8, 11)))

    def test_all_days_in_restricted_period_july_august_2026(self):
        # Every day from Jul 28 to Aug 10 should be in restricted period
        for day_num in range(28, 32):
            with self.subTest(day=f"Jul {day_num}"):
                self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 7, day_num)))
        for day_num in range(1, 11):
            with self.subTest(day=f"Aug {day_num}"):
                self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 8, day_num)))

    def test_days_before_and_after_not_restricted(self):
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 7, 27)))
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 8, 11)))


class RestrictedPeriodDecJanTests(unittest.TestCase):
    """Verify Dec→Jan cross-year: last Fri Dec 26 → Tue Dec 22 → Mon after Jan 1 Fri = Jan 4."""

    def test_dec_22_is_start(self):
        self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 12, 22)))

    def test_jan_4_is_end(self):
        self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2027, 1, 4)))

    def test_dec_21_not_restricted(self):
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 12, 21)))

    def test_jan_5_not_restricted(self):
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2027, 1, 5)))

    def test_all_days_dec_22_to_jan_4(self):
        for day in range(22, 32):
            with self.subTest(day=f"Dec {day}"):
                self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 12, day)))
        for day in range(1, 5):
            with self.subTest(day=f"Jan {day}"):
                self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2027, 1, day)))


class RestrictedPeriodOtherMonthsTests(unittest.TestCase):
    """Verify restricted period for other months in 2026."""

    def test_january_february_2026(self):
        # Jan last Fri = 30, Tue = 27; Feb first Fri = 6, Mon after = 9
        # Restricted: Jan 27 → Feb 9
        self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 1, 27)))
        self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 2, 9)))
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 1, 26)))
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 2, 10)))

    def test_march_april_2026(self):
        # Mar last Fri = 27, Tue = 24; Apr first Fri = 3, Mon after = 6
        # Restricted: Mar 24 → Apr 6
        self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 3, 24)))
        self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 4, 6)))
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 3, 23)))
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 4, 7)))

    def test_mid_month_never_restricted(self):
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 7, 15)))
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(datetime(2026, 8, 20)))


class DeactivatedSlotRestrictedTests(unittest.TestCase):
    """Test that H=12 and H=16 are DO NOT ENTER during restricted period."""

    def test_h12_deactivated_on_restricted_day(self):
        # Jul 28 (Tue of last-Fri week, in restricted): H=12 must be deactivated
        self.assertTrue(mt5_signal_bot.is_deactivated_signal_slot(datetime(2026, 7, 28), 12))

    def test_h16_deactivated_on_restricted_day(self):
        # Aug 10 (Mon after first Fri, in restricted): H=16 must be deactivated
        self.assertTrue(mt5_signal_bot.is_deactivated_signal_slot(datetime(2026, 8, 10), 16))

    def test_h12_NOT_deactivated_outside_restricted(self):
        # Jul 27 (before restricted): H=12 NOT deactivated
        self.assertFalse(mt5_signal_bot.is_deactivated_signal_slot(datetime(2026, 7, 27), 12))

    def test_h16_NOT_deactivated_outside_restricted(self):
        # Aug 11 (after restricted): H=16 NOT deactivated (it's a Tuesday)
        self.assertFalse(mt5_signal_bot.is_deactivated_signal_slot(datetime(2026, 8, 11), 16))

    def test_other_hours_NOT_deactivated_by_restricted(self):
        # H=6, H=9 should NOT be deactivated just because of restricted period
        restricted_day = datetime(2026, 7, 28)
        for hour in (6, 9):
            with self.subTest(hour=hour):
                self.assertFalse(mt5_signal_bot.is_deactivated_signal_slot(restricted_day, hour))

    def test_h16_on_thursday_always_deactivated_even_outside_restricted(self):
        # Thursday outside restricted: H=16 still deactivated (Thursday rule)
        regular_thursday = datetime(2026, 7, 23)  # Thu, outside restricted
        self.assertTrue(mt5_signal_bot.is_deactivated_signal_slot(regular_thursday, 16))

    def test_h12_mid_month_NOT_deactivated(self):
        # Aug 20 (mid-month, not restricted): H=12 NOT deactivated
        self.assertFalse(mt5_signal_bot.is_deactivated_signal_slot(datetime(2026, 8, 20), 12))

    def test_h12_h16_deactivated_in_dec_jan_restricted(self):
        # Dec 22 and Jan 4 are in restricted period → H=12/H=16 deactivated
        self.assertTrue(mt5_signal_bot.is_deactivated_signal_slot(datetime(2026, 12, 22), 12))
        self.assertTrue(mt5_signal_bot.is_deactivated_signal_slot(datetime(2026, 12, 22), 16))
        self.assertTrue(mt5_signal_bot.is_deactivated_signal_slot(datetime(2027, 1, 4), 12))
        self.assertTrue(mt5_signal_bot.is_deactivated_signal_slot(datetime(2027, 1, 4), 16))


class Mt4ServerDeactivatedSlotRestrictedTests(unittest.TestCase):
    """Verify mt4_mt5_server.is_deactivated_slot also respects restricted period."""

    def test_h12_deactivated_on_restricted_day(self):
        self.assertTrue(mt4_mt5_server.is_deactivated_slot(datetime(2026, 7, 28), 12))

    def test_h16_deactivated_on_restricted_day(self):
        self.assertTrue(mt4_mt5_server.is_deactivated_slot(datetime(2026, 8, 10), 16))

    def test_h12_NOT_deactivated_outside_restricted(self):
        self.assertFalse(mt4_mt5_server.is_deactivated_slot(datetime(2026, 7, 27), 12))

    def test_h16_NOT_deactivated_outside_restricted_tuesday(self):
        self.assertFalse(mt4_mt5_server.is_deactivated_slot(datetime(2026, 8, 11), 16))

    def test_existing_deactivation_rules_still_work(self):
        self.assertTrue(mt4_mt5_server.is_deactivated_slot(datetime(2026, 7, 28), 4))
        self.assertTrue(mt4_mt5_server.is_deactivated_slot(datetime(2026, 7, 28), 5))
        self.assertTrue(mt4_mt5_server.is_deactivated_slot(datetime(2026, 8, 6), 3))

    def test_dec_jan_restricted_period(self):
        self.assertTrue(mt4_mt5_server.is_deactivated_slot(datetime(2026, 12, 22), 12))
        self.assertTrue(mt4_mt5_server.is_deactivated_slot(datetime(2027, 1, 4), 16))

    def test_none_returns_false(self):
        self.assertFalse(mt4_mt5_server._is_in_restricted_calendar_period(None))


class NoneEdgeCaseTests(unittest.TestCase):
    def test_none_not_in_restricted_period(self):
        self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(None))

    def test_none_not_deactivated(self):
        self.assertFalse(mt5_signal_bot.is_deactivated_signal_slot(None, 12))
        self.assertFalse(mt5_signal_bot.is_deactivated_signal_slot(None, 16))


if __name__ == "__main__":
    unittest.main()
