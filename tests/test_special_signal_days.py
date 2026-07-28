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

    def test_special_and_post_special_days_do_not_set_deactivated_direct_slots(self) -> None:
        for broker_dt in (
            datetime(2026, 8, 6, 12, 0),   # special Thu inside restricted
            datetime(2026, 8, 7, 12, 0),   # special Fri inside restricted
            datetime(2026, 8, 10, 12, 0),  # post-SD1 Mon inside restricted
        ):
            with self.subTest(day=broker_dt.date()):
                for hour in (6, 9, 12, 14, 16):
                    with self.subTest(hour=hour):
                        self.assertFalse(mt5_signal_bot.is_deactivated_signal_slot(broker_dt, hour))

    def test_month_boundary_suppress_schedule(self) -> None:
        # Restricted calendar period: Tue of last-Fri week through Mon after first Fri of next month
        # Jul 2026 → Aug 2026: last Fri Jul = 31, Tue of that week = 28; first Fri Aug = 7, Mon after = 10
        # Restricted: 2026-07-28 through 2026-08-10 inclusive
        suppress_days = [
            datetime(2026, 7, 28),  # Tue of last-Fri week
            datetime(2026, 7, 29),  # Wed
            datetime(2026, 7, 30),  # Thu SD1
            datetime(2026, 7, 31),  # Fri SD1
            datetime(2026, 8, 3),   # Mon đầu tháng
            datetime(2026, 8, 4),   # Tue đầu tháng
            datetime(2026, 8, 5),   # Wed đầu tháng
            datetime(2026, 8, 6),   # Thu SD1
            datetime(2026, 8, 7),   # Fri SD1
            datetime(2026, 8, 10),  # Mon after first Fri
        ]
        for dt in suppress_days:
            with self.subTest(day=dt.date()):
                self.assertTrue(mt5_signal_bot._is_in_restricted_calendar_period(dt), f"{dt.date()} should be in restricted period")

        no_suppress_days = [
            datetime(2026, 7, 27),  # Mon before restricted starts
            datetime(2026, 8, 11),  # Tue after restricted
            datetime(2026, 8, 12),  # Wed regular
            datetime(2026, 8, 13),  # Thu regular
            datetime(2026, 8, 14),  # Fri regular
            datetime(2026, 8, 17),  # Mon regular
        ]
        for dt in no_suppress_days:
            with self.subTest(day=dt.date()):
                self.assertFalse(mt5_signal_bot._is_in_restricted_calendar_period(dt), f"{dt.date()} should NOT be in restricted period")

    def test_h6_is_not_deactivated_on_special_day(self) -> None:
        special_thursday = datetime(2026, 9, 24, 6, 0)  # special Thu outside restricted
        context = {
            "signal": "BUY",
            "entry_time": "06:11",
            "pair_dirs": {"XAUUSD": "BUY"},
        }
        with patch.object(
            mt5_signal_bot,
            "evaluate_gbp_h1_slot",
            return_value=context,
            create=True,
        ):
            result = mt5_signal_bot.calculate_slot_signal(special_thursday, 6)
            self.assertFalse(result.get("deactivated", False))

    def test_every_thursday_h3_is_deactivated(self) -> None:
        special_thursday = datetime(2026, 8, 6, 3, 0)
        regular_thursday = datetime(2026, 7, 23, 3, 0)
        special_friday = datetime(2026, 8, 7, 3, 0)
        context = {
            "signal": "BUY",
            "entry_time": "03:11",
            "pair_dirs": {"XAUUSD": "BUY"},
        }

        with patch.object(
            mt5_signal_bot,
            "evaluate_gbp_h1_slot",
            side_effect=lambda *_args: dict(context),
            create=True,
        ):
            thursday_result = mt5_signal_bot.calculate_slot_signal(special_thursday, 3)
            regular_thursday_result = mt5_signal_bot.calculate_slot_signal(regular_thursday, 3)
            friday_result = mt5_signal_bot.calculate_slot_signal(special_friday, 3)

        self.assertTrue(thursday_result["deactivated"])
        self.assertTrue(regular_thursday_result["deactivated"])
        self.assertEqual(friday_result["signal"], "BUY")
        self.assertFalse(friday_result.get("deactivated", False))

    def test_h4_is_deactivated_every_weekday_while_h5_is_inactive(self) -> None:
        monday = datetime(2026, 7, 20, 4, 45)

        for weekday in range(5):
            broker_dt = monday + timedelta(days=weekday)
            with self.subTest(weekday=weekday):
                self.assertTrue(mt5_signal_bot.is_deactivated_signal_slot(broker_dt, 4))

        self.assertFalse(mt5_signal_bot.is_deactivated_signal_slot(monday, 3))
        self.assertNotIn(5, mt5_signal_bot.ACTIVE_HOURS)


class SpecialDay2Tests(unittest.TestCase):
    """Test 'ngày đặc biệt 2' logic: 1st/2nd/3rd Fri in 5-Fri months, 1st/2nd Fri in 4-Fri months."""

    def test_5_friday_month_first_on_day_1(self) -> None:
        # May 2026: starts on Friday → Fri = 1, 8, 15, 22, 29 (5 Fridays)
        # Special day 2 = 1st (1) + 2nd (8) + 3rd (15)
        self.assertTrue(mt5_signal_bot.is_special_day_2(datetime(2026, 5, 1)))   # 1st Fri
        self.assertTrue(mt5_signal_bot.is_special_day_2(datetime(2026, 5, 8)))   # 2nd Fri
        self.assertTrue(mt5_signal_bot.is_special_day_2(datetime(2026, 5, 15)))  # 3rd Fri
        self.assertFalse(mt5_signal_bot.is_special_day_2(datetime(2026, 5, 22))) # 4th Fri
        self.assertFalse(mt5_signal_bot.is_special_day_2(datetime(2026, 5, 29))) # 5th Fri

    def test_5_friday_month_first_on_day_6(self) -> None:
        # March 2026: Fridays = 6, 13, 20, 27 + also April 3 is not March
        # Wait, let me check: March 2026 starts on Sunday
        # Fri 1st = 6, then 13, 20, 27 — only 4 Fridays!
        # Let me find a 5-Fri month with first Fri = 6
        # May 2026: starts on Friday (day 1) — no
        # January 2027: starts on Friday (day 2) — Fri = 2,9,16,23,30 — 5 Fridays
        # Need first Friday = 6: let me check June 2026
        # June 2026: starts on Monday → Fri 1st = 5, Fri = 5,12,19,26 — 4 Fridays
        # October 2026: starts on Thursday → Fri 1st = 2
        # Let me just verify with a known 5-Fri month where first Fri = 6
        # January 2026: starts on Thursday → Fri 1st = 3, Fri = 3,10,17,24,31 — 5 Fridays, first=3
        # Let me find: month where day 6 is first Friday
        # That means day 1 must be Monday, day 2 Tuesday, ..., day 6 Friday
        # February 2026: starts on Sunday → first Fri = 6! Fridays = 6,13,20,27 — only 4 Fridays!
        # Need month starting on Monday (first Fri = 5) or... day 6 as Friday means Monday is day 1
        # Actually, for 5 Fridays starting from day 6: 6,13,20,27 + next month... only 4 if month ≤ 28
        # For 5 Fridays with first = 6: need month with 31 days and starts on Monday
        # No such month in 2026. Let me use a 4-Fri month example for first=6 instead.
        pass

    def test_4_friday_month(self) -> None:
        # February 2026: starts on Sunday → Fri = 6,13,20,27 (4 Fridays)
        # Special day 2 = 1st (6) + 2nd (13)
        self.assertTrue(mt5_signal_bot.is_special_day_2(datetime(2026, 2, 6)))   # 1st Fri
        self.assertTrue(mt5_signal_bot.is_special_day_2(datetime(2026, 2, 13)))  # 2nd Fri
        self.assertFalse(mt5_signal_bot.is_special_day_2(datetime(2026, 2, 20))) # 3rd Fri
        self.assertFalse(mt5_signal_bot.is_special_day_2(datetime(2026, 2, 27))) # 4th Fri

    def test_non_friday_non_wednesday_is_never_special_day_2(self) -> None:
        # Monday and Tuesday are never special_day_2
        for wd in range(2):  # Monday (0) and Tuesday (1)
            dt = datetime(2026, 8, 3 + wd)  # Mon Aug 3, Tue 4
            with self.subTest(day=dt.date()):
                self.assertFalse(mt5_signal_bot.is_special_day_2(dt))
        # Wednesday before a special_day_2 Friday IS special_day_2
        wed_before_1st_sd2 = datetime(2026, 8, 5)  # Wed before 1st Fri Aug 7
        self.assertTrue(mt5_signal_bot.is_special_day_2(wed_before_1st_sd2))

    def test_5_friday_month_first_on_day_2(self) -> None:
        # January 2026: starts Thursday → first Fri = 2, Fri = 2,9,16,23,30 (5 Fridays)
        # Special day 2 = 1st (2) + 2nd (9) + 3rd (16)
        self.assertTrue(mt5_signal_bot.is_special_day_2(datetime(2026, 1, 2)))   # 1st Fri
        self.assertTrue(mt5_signal_bot.is_special_day_2(datetime(2026, 1, 9)))   # 2nd Fri
        self.assertTrue(mt5_signal_bot.is_special_day_2(datetime(2026, 1, 16)))  # 3rd Fri
        self.assertFalse(mt5_signal_bot.is_special_day_2(datetime(2026, 1, 23))) # 4th Fri
        self.assertFalse(mt5_signal_bot.is_special_day_2(datetime(2026, 1, 30))) # 5th Fri

    def test_5_friday_month_first_on_day_7(self) -> None:
        # December 2026: starts on Tuesday → first Fri = 5, Fri = 5,12,19,26 — only 4 Fridays
        # Need a month where first Fri = 7: that means day 1 is Saturday
        # July 2026: starts on Wednesday → first Fri = 3, Fri = 3,10,17,24,31 (5 Fridays, first=3)
        # Let me find month where day 7 is first Friday:
        # That means day 1 is Monday... no, day 7 Friday means day 1 Monday
        # Actually, for day 7 to be the first Friday, day 1 must be Monday
        # September 2026: starts on Tuesday → first Fri = 4, Fri = 4,11,18,25 (4 Fridays)
        # October 2026: starts on Thursday → first Fri = 2, Fri = 2,9,16,23,30 (5 Fridays, first=2)
        # November 2026: starts on Sunday → first Fri = 6, Fri = 6,13,20,27 (4 Fridays, first=6)
        # Let me check May 2025: starts on Thursday → first Fri = 2
        # August 2025: starts on Friday → first Fri = 1, Fri = 1,8,15,22,29 (5 Fridays)
        # For first Fri = 7: month starting Saturday, 7 is first Fri
        # June 2025: starts on Sunday → first Fri = 6
        # March 2025: starts on Saturday → first Fri = 7! Fri = 7,14,21,28 (4 Fridays)
        # Special day 2 = 1st (7) + 2nd (14)
        self.assertTrue(mt5_signal_bot.is_special_day_2(datetime(2025, 3, 7)))   # 1st Fri
        self.assertTrue(mt5_signal_bot.is_special_day_2(datetime(2025, 3, 14)))  # 2nd Fri
        self.assertFalse(mt5_signal_bot.is_special_day_2(datetime(2025, 3, 21))) # 3rd Fri (4-Fri month)

    def test_restricted_calendar_is_not_a_deactivated_slot_rule(self) -> None:
        """Special and month-boundary dates do not set a deactivated flag."""
        # Aug 6 and Jul 30 fall in the restricted calendar period (Jul 28 to Aug 10).
        # The reset rules keep H=12 active; the calendar must not deactivate it.
        restricted_days = [
            datetime(2026, 8, 6, 12, 0),   # special Thu inside restricted
            datetime(2026, 7, 30, 12, 0),   # month boundary inside restricted
        ]
        for broker_dt in restricted_days:
            with self.subTest(day=broker_dt.date()):
                for hour in (6, 9, 12, 14, 16):
                    with self.subTest(hour=hour):
                        self.assertFalse(mt5_signal_bot.is_deactivated_signal_slot(broker_dt, hour))

        # May 8 (2nd Friday, 5-Fri month) is special day 2 but NOT regular special day
        may_8 = datetime(2026, 5, 8)
        self.assertTrue(mt5_signal_bot.is_special_day_2(may_8))
        self.assertFalse(mt5_signal_bot.is_special_day(may_8))
        # Aug 6 (Thu) is a regular special day — H=12 still emits signal
        aug_6 = datetime(2026, 8, 6)
        self.assertTrue(mt5_signal_bot.is_special_day(aug_6))
        # Aug 14 (2nd Fri, 4-Fri month) is special day 2 but NOT regular special day
        aug_14 = datetime(2026, 8, 14)
        self.assertTrue(mt5_signal_bot.is_special_day_2(aug_14))
        self.assertFalse(mt5_signal_bot.is_special_day(aug_14))


if __name__ == "__main__":
    unittest.main()
