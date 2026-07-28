from datetime import datetime
import unittest

from controllers.dashboard_controller import _next_desktop_signal


class DesktopSignalScheduleTests(unittest.TestCase):
    def test_h4_uses_the_0400_publication_clock(self):
        slot, target = _next_desktop_signal(datetime(2026, 7, 14, 3, 15))

        self.assertEqual((slot, target.strftime("%H:%M")), (4, "04:00"))

    def test_uses_actual_publication_time_instead_of_blanket_minute_45(self):
        now = datetime(2026, 7, 14, 5, 50)

        slot, target = _next_desktop_signal(now)

        self.assertEqual(slot, 6)
        self.assertEqual(target.strftime("%H:%M"), "06:00")

    def test_skips_weekend_after_friday_last_slot(self):
        now = datetime(2026, 7, 17, 16, 1)

        slot, target = _next_desktop_signal(now)

        self.assertEqual(slot, 3)
        self.assertEqual(target.strftime("%Y-%m-%d %H:%M"), "2026-07-20 03:00")

    def test_special_day_next_slot_is_h9_on_the_normal_clock(self):
        # H=9 remains active on special days and publishes at 09:00.
        slot, target = _next_desktop_signal(datetime(2026, 8, 6, 7, 50))
        self.assertEqual((slot, target.strftime("%H:%M")), (9, "09:00"))

        slot, target = _next_desktop_signal(datetime(2026, 8, 6, 11, 0))
        self.assertEqual((slot, target.strftime("%H:%M")), (12, "12:00"))

    def test_new_year_pair_is_not_special(self):
        slot, target = _next_desktop_signal(datetime(2026, 12, 31, 7, 50))
        self.assertEqual((slot, target.strftime("%H:%M")), (9, "09:00"))

        slot, target = _next_desktop_signal(datetime(2026, 12, 31, 11, 0))
        self.assertEqual((slot, target.strftime("%H:%M")), (12, "12:00"))


if __name__ == "__main__":
    unittest.main()
