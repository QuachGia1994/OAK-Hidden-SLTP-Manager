"""Additional BrokerClock tests for DST/restart edge cases."""

import json
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from domain.broker_clock import BrokerClock, BrokerClockError


def epoch(year, month, day, hour=0, minute=0, second=0):
    return int(datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc).timestamp())


class AdvancingTick:
    def __init__(self, timestamp):
        self.timestamp = timestamp

    def read(self, read_index):
        return SimpleNamespace(time=self.timestamp, time_msc=self.timestamp * 1000 + read_index)


def tick(timestamp):
    return AdvancingTick(timestamp)


class FakeMT5:
    TIMEFRAME_D1 = 16408

    def __init__(self, rates_by_symbol, ticks_by_symbol=None):
        self.rates_by_symbol = rates_by_symbol
        self.ticks_by_symbol = ticks_by_symbol or {}
        self.tick_read_counts = {}
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

    def symbol_info_tick(self, symbol):
        value = self.ticks_by_symbol.get(symbol)
        if isinstance(value, AdvancingTick):
            read_index = self.tick_read_counts.get(symbol, 0)
            self.tick_read_counts[symbol] = read_index + 1
            return value.read(read_index)
        return value

    def copy_rates_range(self, symbol, timeframe, start_utc, end_utc):
        value = self.rates_by_symbol.get(symbol)
        if isinstance(value, Exception):
            raise value
        return value


class BrokerClockExtraTests(unittest.TestCase):
    def test_persist_raises_on_cached_timestamp_mode_conflict(self):
        now_utc = datetime(2026, 7, 22, 12, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = f"{temp_dir}/broker-clock.json"
            # Pre-populate cache with a profile that claims 'utc' timestamp mode
            identity_key = BrokerClock._hash_identity(("Demo", 1))
            payload = {
                "version": 2,
                "profiles": {
                    identity_key: {
                        "timestamp_mode": "utc",
                        "offsets": {},
                        "verified_dates": [],
                    }
                },
            }
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(payload, f)

            # Make MT5 calibrate to a non-zero broker_wall offset (3h)
            mt5 = FakeMT5({"XAUUSD": [{"time": epoch(2026, 7, 22)}]}, {"XAUUSD": tick(epoch(2026, 7, 22, 15))})
            clock = BrokerClock(mt5, cache_path=cache_path)

            # Persist attempt should detect conflict between cached 'utc' and live 'broker_wall'
            with self.assertRaises(BrokerClockError):
                clock.current_utc_offset(now_utc)


if __name__ == "__main__":
    unittest.main()
