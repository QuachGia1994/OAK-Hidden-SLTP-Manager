"""Standardized market-data health contract and selected-profile binding.

Mirrors the acceptance tests required by the edit prompt:
- test_mt5_health_contract
- test_mt4_legacy_health_contract
- test_get_broker_time_accepts_standard_health
- test_health_contract_has_no_dict_object_mismatch
- test_provider_uses_selected_profile_path
- test_provider_does_not_reinitialize_connected_terminal
- test_provider_rejects_wrong_account_or_server
- test_vantage_profile_does_not_fall_back_to_default_terminal
- test_xau_d_source_is_gbpusd
- test_gbpusd_d_source_is_gbpusd
- test_other_gbp_pairs_use_own_d_source
"""
import unittest
from datetime import datetime
from types import SimpleNamespace

from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot
from mt5_signal_bot import MarketDataClockError, get_broker_time, set_market_data_provider
from providers.health_contract import MarketDataHealth, health_value
from providers.mt4_legacy_market_data_provider import MT4LegacyMarketDataProvider
from providers.mt5_market_data_provider import MT5MarketDataProvider


class _FakeMT5:
    """Minimal MT5 module recording initialize() calls."""

    TIMEFRAME_M30 = 30
    TIMEFRAME_H1 = 60
    TIMEFRAME_H4 = 240

    def __init__(self, *, login=88001, server="VantageMarkets-Server", terminal=True, account=True):
        self._login = login
        self._server = server
        self._terminal = terminal
        self._account = account
        self._initialized = True
        self.initialize_calls = 0

    def initialize(self, *args, **kwargs):
        self.initialize_calls += 1
        self.last_init_args = args
        self._initialized = True
        return True

    def shutdown(self):
        return True

    def last_error(self):
        return ""

    def terminal_info(self):
        if not self._terminal or not self._initialized:
            return None
        return SimpleNamespace(time=0, name="MetaTrader 5")

    def account_info(self):
        if not self._account or not self._initialized:
            return None
        return SimpleNamespace(login=self._login, server=self._server, balance=1000.0)

    def symbol_info(self, symbol):
        return SimpleNamespace(name=symbol)

    def symbol_select(self, symbol, enable):
        return True

    def copy_rates_range(self, symbol, timeframe, start, end):
        return []


class _FakeClock:
    def get_broker_utc_offset(self, broker_date=None):
        return 7

    def utc_offset_for_date(self, broker_date):
        return 7

    def is_broker_utc_offset_verified(self, broker_date=None):
        return True


class TestMarketDataHealthContract(unittest.TestCase):
    def test_mt5_health_contract(self):
        provider = MT5MarketDataProvider(mt5_module=_FakeMT5(), broker_clock=_FakeClock())
        health = provider.get_health()
        self.assertIsInstance(health, MarketDataHealth)
        self.assertEqual(health.state, "disconnected")
        self.assertIs(health.fresh, False)
        self.assertIs(health.degraded, False)

    def test_mt4_legacy_health_contract(self):
        provider = MT4LegacyMarketDataProvider(feed_store=None)
        health = provider.get_health()
        self.assertIsInstance(health, MarketDataHealth)
        self.assertEqual(health.state, "disabled")
        self.assertIs(health.fresh, False)

    def test_get_broker_time_accepts_standard_health(self):
        provider = MT5MarketDataProvider(mt5_module=_FakeMT5(), broker_clock=_FakeClock())
        provider._connected = True
        provider._cache[("XAUUSD", "H1")] = [{"time": 1}]

        original = mt5_signal_bot.MARKET_DATA_PROVIDER
        try:
            set_market_data_provider(provider)
            broker_time = get_broker_time()
        finally:
            set_market_data_provider(original)

        self.assertIsNotNone(broker_time)

    def test_get_broker_time_fails_closed_on_stale_standard_health(self):
        provider = MT5MarketDataProvider(mt5_module=_FakeMT5(), broker_clock=_FakeClock())
        provider._connected = False

        original = mt5_signal_bot.MARKET_DATA_PROVIDER
        try:
            set_market_data_provider(provider)
            with self.assertRaises(MarketDataClockError):
                get_broker_time()
        finally:
            set_market_data_provider(original)

    def test_health_contract_has_no_dict_object_mismatch(self):
        # Consumers read via health_value(), so a Mapping-shaped health never
        # triggers "'dict' object has no attribute 'fresh'".
        dict_health = {"fresh": True, "state": "connected", "observed_at_utc": "2026-07-31T00:00:00+00:00"}
        self.assertIs(health_value(dict_health, "fresh", False), True)
        self.assertEqual(health_value(dict_health, "state", "stale"), "connected")
        self.assertEqual(health_value(dict_health, "observed_at_utc", ""), "2026-07-31T00:00:00+00:00")
        self.assertIsNone(health_value(None, "fresh"))

        dataclass_health = MarketDataHealth(
            state="connected", fresh=True, degraded=False,
            age_seconds=0.0, observed_at_utc="", clock_verified=True,
        )
        self.assertIs(health_value(dataclass_health, "fresh", False), True)


class TestProviderProfileBinding(unittest.TestCase):
    VANTAGE_CFG = {
        "path": "C:/Program Files/Vantage/terminal64.exe",
        "login_id": 88001,
        "server": "VantageMarkets-Server",
    }

    def test_provider_uses_selected_profile_path(self):
        provider = MT5MarketDataProvider(mt5_module=_FakeMT5(), broker_clock=_FakeClock())
        provider.bind_profile(self.VANTAGE_CFG)
        self.assertEqual(provider._conf.get("mt5_path"), "C:/Program Files/Vantage/terminal64.exe")

    def test_provider_does_not_reinitialize_connected_terminal(self):
        fake = _FakeMT5(login=88001, server="VantageMarkets-Server")
        provider = MT5MarketDataProvider(mt5_module=fake, broker_clock=_FakeClock())
        provider.bind_profile(self.VANTAGE_CFG)

        self.assertTrue(provider.connect(reuse_existing_session=True))
        self.assertEqual(fake.initialize_calls, 0)
        self.assertTrue(provider._connected)

    def test_provider_rejects_wrong_account(self):
        fake = _FakeMT5(login=88001, server="VantageMarkets-Server")
        provider = MT5MarketDataProvider(mt5_module=fake, broker_clock=_FakeClock())
        provider.bind_profile(dict(self.VANTAGE_CFG, login_id=99999))

        self.assertFalse(provider.connect(reuse_existing_session=True))
        self.assertFalse(provider._connected)

    def test_provider_rejects_wrong_server(self):
        fake = _FakeMT5(login=88001, server="ICMarkets-Server")
        provider = MT5MarketDataProvider(mt5_module=fake, broker_clock=_FakeClock())
        provider.bind_profile(self.VANTAGE_CFG)

        self.assertFalse(provider.connect(reuse_existing_session=True))
        self.assertFalse(provider._connected)

    def test_vantage_profile_does_not_fall_back_to_default_terminal(self):
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            terminal_path = os.path.join(tmp, "terminal64.exe")
            with open(terminal_path, "w", encoding="utf-8") as handle:
                handle.write("stub")
            fake = _FakeMT5(login=88001, server="VantageMarkets-Server")
            fake._initialized = False
            provider = MT5MarketDataProvider(mt5_module=fake, broker_clock=_FakeClock())
            provider.bind_profile({"path": terminal_path})

            self.assertTrue(provider.connect(reuse_existing_session=True))
            self.assertEqual(fake.last_init_args, (terminal_path,))


class TestPreloadCoverage(unittest.TestCase):
    def test_preload_without_bars_is_incomplete_and_fail_closed(self):
        fake = _FakeMT5(login=88001, server="VantageMarkets-Server")
        provider = MT5MarketDataProvider(mt5_module=fake, broker_clock=_FakeClock())
        provider.bind_profile({"path": "C:/x/terminal64.exe"})
        result = provider.preload(symbols=("XAUUSD", "GBPUSD"), timeframes=("M30", "H1", "H4"), days=60)

        self.assertIs(result.complete, False)
        self.assertEqual(result.attempted, 6)
        self.assertEqual(len(result.missing), 6)


class TestDSourceSymbolMapping(unittest.TestCase):
    def test_xau_d_source_is_gbpusd(self):
        self.assertEqual(mt5_signal_bot.D_SOURCE_SYMBOL["XAUUSD"], "GBPUSD")

    def test_gbpusd_d_source_is_gbpusd(self):
        self.assertEqual(mt5_signal_bot.D_SOURCE_SYMBOL["GBPUSD"], "GBPUSD")

    def test_other_gbp_pairs_use_own_d_source(self):
        for symbol in ("GBPAUD", "GBPJPY", "GBPCAD"):
            with self.subTest(symbol=symbol):
                self.assertEqual(mt5_signal_bot.D_SOURCE_SYMBOL[symbol], symbol)


if __name__ == "__main__":
    unittest.main()
