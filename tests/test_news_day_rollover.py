import unittest
from datetime import datetime
from oak_trading_reminders import (
    _get_display_tz,
    _get_news_day,
    _get_news_day_str,
    _news_lines_to_dashboard_items,
)
from mt5_signal_bot import _parse_news_for_dashboard


class NewsDayRolloverTests(unittest.TestCase):
    def test_news_day_stays_previous_before_six_local(self):
        tz = _get_display_tz()
        now = datetime(2026, 7, 15, 5, 59, tzinfo=tz)

        self.assertEqual(_get_news_day(now).isoformat(), "2026-07-14")

    def test_news_day_rolls_at_six_local(self):
        tz = _get_display_tz()
        now = datetime(2026, 7, 15, 6, 0, tzinfo=tz)

        self.assertEqual(_get_news_day(now).isoformat(), "2026-07-15")

    def test_dashboard_news_parser_keeps_current_news_day_cache(self):
        news_day = _get_news_day_str()

        items = _parse_news_for_dashboard(
            ["• 19:30 USD 🔴 [HIGH] Core PPI m/m"],
            source_date=news_day,
        )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["date"], news_day)
        self.assertEqual(items[0]["time"], "19:30")

    def test_daily_briefing_empty_news_clears_dashboard_items(self):
        items = _news_lines_to_dashboard_items(
            ["No important news (High Impact) today."],
            "2026-07-15",
        )

        self.assertEqual(items, [])


if __name__ == "__main__":
    unittest.main()
