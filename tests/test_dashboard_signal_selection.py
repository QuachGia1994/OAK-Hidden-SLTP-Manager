import unittest
import json
import os
import tempfile
from datetime import datetime, time, timezone
from unittest.mock import patch

from mt5_signal_bot import _latest_today_news_cache, _parse_news_for_dashboard, get_pair_direction, select_signals_for_dashboard
from oak_trading_reminders import (
    _NEWS_CACHE_VERSION,
    _get_display_tz,
    _get_display_tz_name,
    _get_news_day,
    fetch_forexfactory_xml,
)


class _FakeResponse:
    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self):
        return self._data


class DashboardSignalSelectionTests(unittest.TestCase):
    def test_keeps_all_signal_days_when_pair_dirs_exist(self):
        signals = [
            {"date": "2026-07-03", "hour": 4, "pair_dirs": {"XAUUSD": "BUY"}},
            {"date": "2026-07-03", "hour": 5, "pair_dirs": {"XAUUSD": "SELL"}},
            {"date": "2026-07-04", "hour": 4, "pair_dirs": {"XAUUSD": "BUY"}},
            {"date": "2026-07-04", "hour": 5, "pair_dirs": {}},
        ]

        result = select_signals_for_dashboard(signals)

        self.assertEqual(
            result,
            [
                {"date": "2026-07-03", "hour": 4, "pair_dirs": {"XAUUSD": "BUY"}},
                {"date": "2026-07-03", "hour": 5, "pair_dirs": {"XAUUSD": "SELL"}},
                {"date": "2026-07-04", "hour": 4, "pair_dirs": {"XAUUSD": "BUY"}},
            ],
        )

    def test_h7_active_returns_pair_dirs(self):
        """H=7 is now active — pair_dirs should contain XAUUSD."""
        for broker_dt in (
            datetime(2026, 7, 7, tzinfo=timezone.utc),
            datetime(2026, 7, 9, tzinfo=timezone.utc),
        ):
            with self.subTest(weekday=broker_dt.weekday()):
                    self.assertIn(
                        "XAUUSD",
                        get_pair_direction(7, "BUY", broker_dt)
                    )

    def test_news_parse_marks_system_display_timezone(self):
        item = _parse_news_for_dashboard(["19:30 CAD [HIGH] Employment Change"])[0]
        self.assertEqual(item["local_time"], "19:30")
        self.assertEqual(item["time_zone"], _get_display_tz_name())

    def test_old_news_cache_does_not_become_today_news(self):
        result = _parse_news_for_dashboard(
            ["19:30 CAD [HIGH] Employment Change"],
            source_date="2026-07-10",
        )
        self.assertEqual(result, [])

    def test_forexfactory_xml_uses_utc_to_system_display_time(self):
        display_tz = _get_display_tz()
        today = _get_news_day()
        xml = f"""<weeklyevents>
            <event>
                <title>Core CPI m/m</title>
                <country>USD</country>
                <date>{today.strftime("%m-%d-%Y")}</date>
                <time>12:30pm</time>
                <impact>High</impact>
            </event>
        </weeklyevents>""".encode("utf-8")
        expected_time = datetime.combine(today, time(12, 30), tzinfo=timezone.utc).astimezone(display_tz).strftime("%H:%M")

        with patch("urllib.request.urlopen", return_value=_FakeResponse(xml)):
            result = fetch_forexfactory_xml(lang="EN")

        self.assertEqual(result, [f"• {expected_time} USD 🔴 [HIGH] Core CPI m/m"])

    def test_latest_news_cache_ignores_stale_versions(self):
        today = datetime.now(_get_display_tz()).date().isoformat()
        with tempfile.TemporaryDirectory() as temp_dir, patch("mt5_signal_bot.os.path.abspath", return_value=os.path.join(temp_dir, "mt5_signal_bot.py")):
            stale_path = os.path.join(temp_dir, "news_cache_EN.json")
            with open(stale_path, "w", encoding="utf-8") as f:
                json.dump({"date": today, "v": _NEWS_CACHE_VERSION - 1, "news": ["• 23:30 USD 🔴 [HIGH] CPI m/m"]}, f)

            self.assertIsNone(_latest_today_news_cache())


if __name__ == "__main__":
    unittest.main()
