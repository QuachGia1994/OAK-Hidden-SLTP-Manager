"""MT5 market-data provider and signal-input coverage tests."""
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import mt5_signal_bot
from providers.mt5_market_data_provider import MT5MarketDataProvider


class FakeMT5:
    TIMEFRAME_M30 = 30
    TIMEFRAME_H1 = 60
    TIMEFRAME_H4 = 240

    def __init__(self):
        self.initialized = False
        self.selected = []
        self._rates = {
            "XAUUSD": [
                {"time": int(datetime(2026, 7, 31, 17, tzinfo=timezone.utc).timestamp()), "open": 2400, "high": 2410, "low": 2395, "close": 2405, "tick_volume": 10},
            ]
        }

    def initialize(self, path=None):
        self.initialized = True
        return True

    def terminal_info(self):
        return SimpleNamespace(time=int(datetime(2026, 8, 3, 7, tzinfo=timezone.utc).timestamp()), trade_allowed=True)

    def account_info(self):
        return SimpleNamespace(login=12345, server="VantageMarkets-Live 3", currency="USD")

    def symbol_info(self, symbol):
        return SimpleNamespace(name=symbol)

    def symbol_select(self, symbol, enabled):
        if enabled:
            self.selected.append(symbol)
        return True

    def symbol_info_tick(self, symbol):
        return SimpleNamespace(time=int(datetime.now(timezone.utc).timestamp()))

    def copy_rates_range(self, symbol, timeframe, start, end):
        return self._rates.get(symbol, [])


class FixedClock:
    def utc_offset_for_date(self, _date):
        return 3

    def is_broker_utc_offset_verified(self, _date=None):
        return True


class MT5ProviderTests(unittest.TestCase):
    def test_connect_reuses_matching_live_profile(self):
        mt5 = FakeMT5()
        provider = MT5MarketDataProvider(mt5_module=mt5, broker_clock=FixedClock())
        provider.bind_profile({"login_id": 12345, "server": "VantageMarkets-Live 3"})

        self.assertTrue(provider.connect())
        self.assertTrue(provider._connected)
        self.assertEqual(mt5.selected, [])

    def test_rejects_profile_with_wrong_login(self):
        mt5 = FakeMT5()
        provider = MT5MarketDataProvider(mt5_module=mt5, broker_clock=FixedClock())
        provider.bind_profile({"login_id": 99999, "server": "VantageMarkets-Live 3"})

        self.assertFalse(provider.connect())
        self.assertIn("does not match selected profile", provider._health_error)

    def test_preload_normalizes_mt5_rows(self):
        mt5 = FakeMT5()
        provider = MT5MarketDataProvider(mt5_module=mt5, broker_clock=FixedClock())
        provider.bind_profile({"login_id": 12345, "server": "VantageMarkets-Live 3"})

        result = provider.preload(symbols=["XAUUSD"], timeframes=["H1"], days=1)

        self.assertEqual(result.attempted, 1)
        self.assertEqual(result.loaded, 1)
        self.assertTrue(result.complete)
        bars = provider.get_bars("XAUUSD", "H1", datetime(2026, 7, 31, 19), datetime(2026, 7, 31, 21))
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0]["source_id"], "mt5")
        self.assertEqual(bars[0]["resolved_symbol"], "XAUUSD")

    def test_exact_bar_cache_miss_fetches_from_mt5(self):
        mt5 = FakeMT5()
        provider = MT5MarketDataProvider(mt5_module=mt5, broker_clock=FixedClock())
        provider.bind_profile({"login_id": 12345, "server": "VantageMarkets-Live 3"})
        self.assertTrue(provider.connect())

        bar = provider.get_exact_bar("XAUUSD", "H1", datetime(2026, 7, 31, 20))

        self.assertIsNotNone(bar)
        self.assertEqual(bar["close"], 2405.0)

    def test_health_is_connected_after_successful_preload(self):
        mt5 = FakeMT5()
        provider = MT5MarketDataProvider(mt5_module=mt5, broker_clock=FixedClock())
        provider.bind_profile({"login_id": 12345, "server": "VantageMarkets-Live 3"})
        provider.connect()
        provider.preload(symbols=["XAUUSD"], timeframes=["H1"], days=1)

        health = provider.get_health()

        self.assertEqual(health.state, "connected")
        self.assertTrue(health.fresh)
        self.assertTrue(health.clock_verified)


class MissingInputPolicyTests(unittest.TestCase):
    def test_rebuild_does_not_mark_wait_mt5_data_as_complete(self):
        record = {
            "rebuild_state": "READY",
            "pair_signal_states": {"XAUUSD": "WAIT"},
            "wait_reasons": {"XAUUSD": "WAIT_MT5_DATA"},
        }
        self.assertFalse(mt5_signal_bot._compute_rebuild_complete([record]))

    def test_missing_input_state_is_incomplete(self):
        record = {
            "rebuild_state": "MISSING_INPUT",
            "incomplete": True,
            "missing_inputs": ["WAIT_MT5_DATA"],
            "pair_signal_states": {},
        }
        self.assertFalse(mt5_signal_bot._compute_rebuild_complete([record]))


if __name__ == "__main__":
    unittest.main()
