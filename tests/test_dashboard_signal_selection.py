import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from mt5_signal_bot import _parse_news_for_dashboard, get_pair_direction, select_signals_for_dashboard
from oak_trading_reminders import _get_vn_tz, fetch_forexfactory_xml


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
            {"date": "2026-07-03", "hour": 2, "pair_dirs": {"XAUUSD": "BUY"}},
            {"date": "2026-07-03", "hour": 3, "pair_dirs": {"XAUUSD": "SELL"}},
            {"date": "2026-07-04", "hour": 2, "pair_dirs": {"XAUUSD": "BUY"}},
            {"date": "2026-07-04", "hour": 3, "pair_dirs": {}},
        ]

        result = select_signals_for_dashboard(signals)

        self.assertEqual(
            result,
            [
                {"date": "2026-07-03", "hour": 2, "pair_dirs": {"XAUUSD": "BUY"}},
                {"date": "2026-07-03", "hour": 3, "pair_dirs": {"XAUUSD": "SELL"}},
                {"date": "2026-07-04", "hour": 2, "pair_dirs": {"XAUUSD": "BUY"}},
            ],
        )

    def test_h6_xauusd_only_no_gbp_pair_dirs(self):
        """H=5-8: Focus GA only — pair_dirs has XAU only (no GBP map)."""
        for broker_dt in (
            datetime(2026, 7, 7, tzinfo=timezone.utc),
            datetime(2026, 7, 9, tzinfo=timezone.utc),
        ):
            with self.subTest(weekday=broker_dt.weekday()):
                    self.assertEqual(
                        get_pair_direction(6, "BUY", broker_dt),
                        {"XAUUSD": "BUY"},
                    )

    def test_news_parse_marks_vietnam_timezone(self):
        item = _parse_news_for_dashboard(["19:30 CAD [HIGH] Employment Change"])[0]
        self.assertEqual(item["local_time"], "19:30")
        self.assertEqual(item["time_zone"], "Asia/Bangkok")

    def test_old_news_cache_does_not_become_today_news(self):
        result = _parse_news_for_dashboard(
            ["19:30 CAD [HIGH] Employment Change"],
            source_date="2026-07-10",
        )
        self.assertEqual(result, [])

    def test_forexfactory_xml_uses_utc_to_vietnam_time(self):
        today = datetime.now(_get_vn_tz()).strftime("%m-%d-%Y")
        xml = f"""<weeklyevents>
            <event>
                <title>Core CPI m/m</title>
                <country>USD</country>
                <date>{today}</date>
                <time>12:30pm</time>
                <impact>High</impact>
            </event>
        </weeklyevents>""".encode("utf-8")

        with patch("urllib.request.urlopen", return_value=_FakeResponse(xml)):
            result = fetch_forexfactory_xml(lang="EN")

        self.assertEqual(result, ["• 19:30 USD 🔴 [HIGH] Core CPI m/m"])


if __name__ == "__main__":
    unittest.main()
