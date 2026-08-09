import unittest
from datetime import date, datetime, timedelta


class _HistoryProvider:
    name = "MT5"

    def __init__(self):
        self.bars = {}

    def add(self, symbol, session_date, opening, closing):
        self.bars.setdefault((symbol, "H4"), []).append({
            "broker_dt": datetime.combine(session_date, datetime.min.time()).replace(hour=20),
            "open": opening,
            "high": max(opening, closing),
            "low": min(opening, closing),
            "close": closing,
            "is_complete": True,
            "source_id": "mt5",
        })

    def get_bars(self, symbol, timeframe, start_broker, end_broker):
        return [
            bar for bar in self.bars.get((symbol, timeframe), [])
            if start_broker <= bar["broker_dt"] <= end_broker
        ]


class TestDHistoryDateIsolation(unittest.TestCase):
    def test_each_target_date_selects_its_own_previous_session_window(self):
        provider = _HistoryProvider()
        for session_date, opening, closing in (
            (date(2026, 7, 28), 1.0, 2.0),
            (date(2026, 7, 29), 2.0, 1.0),
            (date(2026, 7, 30), 3.0, 4.0),
        ):
            provider.add("GBPUSD", session_date, opening, closing)

        for target_date, expected_session in (
            (date(2026, 7, 29), date(2026, 7, 28)),
            (date(2026, 7, 30), date(2026, 7, 29)),
            (date(2026, 7, 31), date(2026, 7, 30)),
        ):
            start = datetime.combine(expected_session, datetime.min.time()).replace(hour=20)
            end = start + timedelta(hours=4)
            bars = provider.get_bars("GBPUSD", "H4", start, end)
            self.assertEqual(len(bars), 1)
            self.assertEqual(bars[0]["broker_dt"].date(), expected_session)


if __name__ == "__main__":
    unittest.main()
