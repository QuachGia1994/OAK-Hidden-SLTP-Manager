"""Tests for fail-closed MT5 broker-calendar conversion."""

import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace

from domain.broker_clock import BrokerClock, BrokerClockError


def utc_timestamp(year, month, day, hour):
    return int(datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp())


class FakeMT5:
    TIMEFRAME_D1 = 16408

    def __init__(self, rates_by_symbol):
        self.rates_by_symbol = rates_by_symbol
        self.calls = []
        self.connected = True
        self.identity = ("Demo", 1)

    def terminal_info(self):
        return object() if self.connected else None

    def account_info(self):
        if not self.connected:
            return None
        return SimpleNamespace(server=self.identity[0], login=self.identity[1])

    def symbol_select(self, _symbol, _enabled):
        return True

    def copy_rates_range(self, symbol, timeframe, start_utc, end_utc):
        self.calls.append((symbol, timeframe, start_utc, end_utc))
        value = self.rates_by_symbol.get(symbol)
        if isinstance(value, Exception):
            raise value
        return value


class BrokerClockTests(unittest.TestCase):
    def test_derives_and_caches_date_specific_offset_from_xau_d1_open(self):
        mt5 = FakeMT5({"XAUUSD": [{"time": utc_timestamp(2026, 7, 21, 21)}]})
        clock = BrokerClock(mt5)

        self.assertEqual(clock.utc_offset_for_date(date(2026, 7, 22)), 3)
        self.assertEqual(clock.utc_offset_for_date(date(2026, 7, 22)), 3)
        self.assertEqual(len(mt5.calls), 1)

    def test_falls_back_to_gbpusd_when_xau_history_is_unavailable(self):
        mt5 = FakeMT5({
            "XAUUSD": None,
            "GBPUSD": [{"time": utc_timestamp(2026, 7, 21, 21)}],
        })

        self.assertEqual(BrokerClock(mt5).utc_offset_for_date(date(2026, 7, 22)), 3)
        self.assertEqual([call[0] for call in mt5.calls], ["XAUUSD", "GBPUSD"])

    def test_allows_one_hour_dst_transition(self):
        mt5 = FakeMT5({
            "XAUUSD": [
                {"time": utc_timestamp(2026, 3, 26, 22)},
                {"time": utc_timestamp(2026, 3, 29, 21)},
            ]
        })
        clock = BrokerClock(mt5)

        self.assertEqual(clock.utc_offset_for_date(date(2026, 3, 27)), 2)
        self.assertEqual(clock.utc_offset_for_date(date(2026, 3, 30)), 3)

    def test_rejects_inconsistent_multi_hour_offset_change(self):
        mt5 = FakeMT5({
            "XAUUSD": [
                {"time": utc_timestamp(2026, 7, 20, 22)},
                {"time": utc_timestamp(2026, 7, 21, 20)},
            ],
            "GBPUSD": [{"time": utc_timestamp(2026, 7, 21, 21)}],
        })

        with self.assertRaisesRegex(BrokerClockError, "more than one hour"):
            BrokerClock(mt5).utc_offset_for_date(date(2026, 7, 22))
        self.assertEqual([call[0] for call in mt5.calls], ["XAUUSD"])

    def test_fails_closed_when_both_symbols_are_unavailable(self):
        mt5 = FakeMT5({"XAUUSD": None, "GBPUSD": None})

        with self.assertRaisesRegex(BrokerClockError, "cannot derive"):
            BrokerClock(mt5).utc_offset_for_date(date(2026, 7, 22))

    def test_current_offset_uses_recent_d1_bar_and_then_cache(self):
        mt5 = FakeMT5({"XAUUSD": [{"time": utc_timestamp(2026, 7, 21, 21)}]})
        clock = BrokerClock(mt5)
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)

        self.assertEqual(clock.current_utc_offset(now_utc), 3)
        self.assertEqual(clock.current_utc_offset(now_utc), 3)
        self.assertEqual(clock.now(now_utc), datetime(2026, 7, 22, 15))
        self.assertEqual(len(mt5.calls), 1)

    def test_current_offset_does_not_use_cache_after_terminal_disconnects(self):
        mt5 = FakeMT5({"XAUUSD": [{"time": utc_timestamp(2026, 7, 21, 21)}]})
        clock = BrokerClock(mt5)
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        self.assertEqual(clock.current_utc_offset(now_utc), 3)
        mt5.connected = False

        with self.assertRaisesRegex(BrokerClockError, "terminal is unavailable"):
            clock.current_utc_offset(now_utc)

    def test_switching_broker_account_invalidates_cached_offset(self):
        mt5 = FakeMT5({"XAUUSD": [{"time": utc_timestamp(2026, 7, 21, 21)}]})
        clock = BrokerClock(mt5)
        broker_date = date(2026, 7, 22)
        self.assertEqual(clock.utc_offset_for_date(broker_date), 3)
        mt5.identity = ("Other", 2)
        mt5.rates_by_symbol["XAUUSD"] = [{"time": utc_timestamp(2026, 7, 21, 22)}]

        self.assertEqual(clock.utc_offset_for_date(broker_date), 2)

    def test_converts_historical_broker_datetime_with_that_dates_offset(self):
        mt5 = FakeMT5({"XAUUSD": [{"time": utc_timestamp(2026, 3, 29, 21)}]})
        clock = BrokerClock(mt5)

        converted = clock.utc_from_broker_datetime(datetime(2026, 3, 30, 16, 0))

        self.assertEqual(converted, datetime(2026, 3, 30, 13, 0, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
