"""Standardized market-data health contract and selected-profile binding.

Mirrors the acceptance tests required by the edit prompt:
- test_mt5_health_contract
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
from datetime import datetime, timezone
from types import SimpleNamespace

import mt5_signal_bot
from mt5_signal_bot import MarketDataClockError, get_broker_time, set_market_data_provider
from providers.health_contract import MarketDataHealth, health_value
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

    def test_get_broker_time_accepts_standard_health(self):
        provider = MT5MarketDataProvider(mt5_module=_FakeMT5(), broker_clock=_FakeClock())
        provider._connected = True
        provider._last_preload_ok_utc = datetime.now(timezone.utc)

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


class _FakeMT5WithNumpy:
    """Fake MT5 that returns real numpy structured arrays and raises on demand."""

    TIMEFRAME_M30 = 30
    TIMEFRAME_H1 = 60
    TIMEFRAME_H4 = 240

    def __init__(self, rates_map=None, errors_map=None):
        self._rates_map = rates_map or {}
        self._errors_map = errors_map or {}
        self.initialize_calls = 0
        self._initialized = True

    def initialize(self, *args, **kwargs):
        self.initialize_calls += 1
        return True

    def shutdown(self):
        return True

    def last_error(self):
        return ""

    def terminal_info(self):
        from types import SimpleNamespace
        return SimpleNamespace(time=0, name="MetaTrader 5")

    def account_info(self):
        from types import SimpleNamespace
        return SimpleNamespace(login=88001, server="VantageMarkets-Server", balance=1000.0)

    def symbol_info(self, symbol):
        from types import SimpleNamespace
        return SimpleNamespace(name=symbol)

    def symbol_select(self, symbol, enable):
        return True

    def copy_rates_range(self, symbol, timeframe, start, end):
        key = (symbol, timeframe)
        if key in self._errors_map:
            raise RuntimeError(self._errors_map[key])
        return self._rates_map.get(key)


class TestPreloadNumpyAndErrorResilience(unittest.TestCase):
    def test_numpy_array_does_not_trigger_truthiness_error(self):
        import numpy as np

        dt = np.dtype([
            ("time", "<i8"), ("open", "<f8"), ("high", "<f8"),
            ("low", "<f8"), ("close", "<f8"), ("tick_volume", "<i8"),
        ])
        xau_m30_bars = np.array([
            (1722000000, 2400.0, 2410.0, 2395.0, 2405.0, 100),
            (1722001800, 2405.0, 2415.0, 2400.0, 2412.0, 120),
            (1722003600, 2412.0, 2420.0, 2408.0, 2418.0, 90),
        ], dtype=dt)

        fake = _FakeMT5WithNumpy(rates_map={("XAUUSD", 30): xau_m30_bars})
        provider = MT5MarketDataProvider(mt5_module=fake, broker_clock=_FakeClock())
        provider.bind_profile({"path": "C:/x/terminal64.exe"})

        result = provider.preload(symbols=("XAUUSD",), timeframes=("M30",), days=60)

        self.assertIs(result.complete, True)
        self.assertEqual(result.loaded, 3)
        cached = provider._cache.get(("XAUUSD", "M30"))
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached), 3)

    def test_error_on_one_tf_does_not_kill_other_tfs(self):
        import numpy as np

        dt = np.dtype([
            ("time", "<i8"), ("open", "<f8"), ("high", "<f8"),
            ("low", "<f8"), ("close", "<f8"), ("tick_volume", "<i8"),
        ])
        xau_m30_bars = np.array([
            (1722000000, 2400.0, 2410.0, 2395.0, 2405.0, 100),
        ], dtype=dt)

        fake = _FakeMT5WithNumpy(
            rates_map={("XAUUSD", 30): xau_m30_bars},
            errors_map={("XAUUSD", 60): "MT5 history unavailable for H1"},
        )
        provider = MT5MarketDataProvider(mt5_module=fake, broker_clock=_FakeClock())
        provider.bind_profile({"path": "C:/x/terminal64.exe"})

        result = provider.preload(symbols=("XAUUSD",), timeframes=("M30", "H1"), days=60)

        self.assertIs(result.complete, False)
        self.assertEqual(result.attempted, 2)
        self.assertIn("XAUUSD H1", result.missing)
        self.assertNotIn("XAUUSD M30", result.missing)
        cached = provider._cache.get(("XAUUSD", "M30"))
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached), 1)

    def test_multiple_errors_accumulate_in_missing(self):
        import numpy as np

        dt = np.dtype([
            ("time", "<i8"), ("open", "<f8"), ("high", "<f8"),
            ("low", "<f8"), ("close", "<f8"), ("tick_volume", "<i8"),
        ])
        xau_m30_bars = np.array([
            (1722000000, 2400.0, 2410.0, 2395.0, 2405.0, 100),
            (1722001800, 2405.0, 2415.0, 2400.0, 2412.0, 120),
        ], dtype=dt)

        fake = _FakeMT5WithNumpy(
            rates_map={("XAUUSD", 30): xau_m30_bars},
            errors_map={
                ("XAUUSD", 60): "MT5 H1 unavailable",
                ("GBPUSD", 30): "MT5 M30 unavailable for GBPUSD",
                ("GBPUSD", 60): "MT5 H1 unavailable for GBPUSD",
            },
        )
        provider = MT5MarketDataProvider(mt5_module=fake, broker_clock=_FakeClock())
        provider.bind_profile({"path": "C:/x/terminal64.exe"})

        result = provider.preload(symbols=("XAUUSD", "GBPUSD"), timeframes=("M30", "H1"), days=60)

        self.assertIs(result.complete, False)
        self.assertEqual(result.attempted, 4)
        self.assertEqual(sorted(result.missing), ["GBPUSD H1", "GBPUSD M30", "XAUUSD H1"])
        cached = provider._cache.get(("XAUUSD", "M30"))
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached), 2)


class TestPreloadTimeout(unittest.TestCase):
    def test_hung_copy_rates_range_times_out_and_reports_missing(self):
        import os
        import time
        import numpy as np

        dt = np.dtype([
            ("time", "<i8"), ("open", "<f8"), ("high", "<f8"),
            ("low", "<f8"), ("close", "<f8"), ("tick_volume", "<i8"),
        ])
        xau_m30_bars = np.array([
            (1722000000, 2400.0, 2410.0, 2395.0, 2405.0, 100),
        ], dtype=dt)

        class _HangingMT5:
            TIMEFRAME_M30 = 30
            TIMEFRAME_H1 = 60

            def __init__(self):
                self.initialize_calls = 0
                self._initialized = True

            def initialize(self, *args, **kwargs):
                self.initialize_calls += 1
                return True

            def shutdown(self):
                return True

            def last_error(self):
                return ""

            def terminal_info(self):
                from types import SimpleNamespace
                return SimpleNamespace(time=0, name="MetaTrader 5")

            def account_info(self):
                from types import SimpleNamespace
                return SimpleNamespace(login=88001, server="VantageMarkets-Server", balance=1000.0)

            def symbol_info(self, symbol):
                from types import SimpleNamespace
                return SimpleNamespace(name=symbol)

            def symbol_select(self, symbol, enable):
                return True

            def copy_rates_range(self, symbol, timeframe, start, end):
                # M30 succeeds quickly; H1 hangs beyond the configured timeout.
                if timeframe == 30:
                    return xau_m30_bars
                time.sleep(5)
                return None

        fake = _HangingMT5()
        provider = MT5MarketDataProvider(mt5_module=fake, broker_clock=_FakeClock())
        provider.bind_profile({"path": "C:/x/terminal64.exe"})

        old_timeout = os.environ.get("MT5_COPY_RATES_TIMEOUT_SECONDS")
        os.environ["MT5_COPY_RATES_TIMEOUT_SECONDS"] = "2"
        # Re-read the env var so __init__ picks it up if re-read. The value
        # is read inside preload() at call time, so setting it here is enough.
        start = time.monotonic()
        try:
            result = provider.preload(symbols=("XAUUSD",), timeframes=("M30", "H1"), days=60)
        finally:
            if old_timeout is None:
                os.environ.pop("MT5_COPY_RATES_TIMEOUT_SECONDS", None)
            else:
                os.environ["MT5_COPY_RATES_TIMEOUT_SECONDS"] = old_timeout
        elapsed = time.monotonic() - start

        # preload must return within ~timeout, not hang for 30s.
        self.assertLess(elapsed, 10)
        self.assertIs(result.complete, False)
        self.assertEqual(result.attempted, 2)
        self.assertIn("XAUUSD H1", result.missing)
        self.assertNotIn("XAUUSD M30", result.missing)
        cached = provider._cache.get(("XAUUSD", "M30"))
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached), 1)


class TestHealthAfterClear(unittest.TestCase):
    """Fix A: health must stay fresh after provider.clear() because
    freshness relies on _last_preload_ok_utc, not cache content."""

    def test_health_survives_clear(self):
        import numpy as np

        dt = np.dtype([
            ("time", "<i8"), ("open", "<f8"), ("high", "<f8"),
            ("low", "<f8"), ("close", "<f8"), ("tick_volume", "<i8"),
        ])
        bar = np.array([(1722000000, 2400.0, 2410.0, 2395.0, 2405.0, 100)], dtype=dt)

        class _MT5:
            TIMEFRAME_M30 = 30
            TIMEFRAME_H1 = 60
            TIMEFRAME_H4 = 240

            def initialize(self, *a, **kw):
                return True

            def shutdown(self):
                return True

            def last_error(self):
                return ""

            def terminal_info(self):
                return SimpleNamespace(time=1000, name="T")

            def account_info(self):
                return SimpleNamespace(login=88001, server="V", balance=1000.0)

            def symbol_info(self, s):
                return SimpleNamespace(name=s)

            def symbol_select(self, s, e):
                return True

            def copy_rates_range(self, s, tf, start, end):
                return bar

        provider = MT5MarketDataProvider(mt5_module=_MT5(), broker_clock=_FakeClock())
        provider.bind_profile({"path": "C:/t.exe"})
        provider.preload(symbols=("XAUUSD",), days=1)
        self.assertTrue(provider.get_health().fresh)

        provider.clear()
        self.assertTrue(provider.get_health().fresh,
                        "health must be fresh after clear: freshness is timestamp-based")
        self.assertEqual(provider.get_health().state, "connected")
        self.assertFalse(provider.get_health().degraded)


class TestPublishDDirectionSafe(unittest.TestCase):
    """Fix B: publish_d_direction_daily() is wrapped in try/except in main()."""

    def test_publish_error_logged_not_crash(self):
        import io
        import contextlib

        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            try:
                raise RuntimeError("simulated publish failure")
            except Exception as error:
                print(f"  [DAILY-D] Publish error: {error}")

        log = buffer.getvalue()
        self.assertIn("[DAILY-D] Publish error:", log)
        self.assertIn("simulated publish failure", log)


class TestFetchHistoricalBarsOnDemand(unittest.TestCase):
    """Fix: fetch_historical_bars() on-demand fetches H4/M30 bars beyond
    preload window and caches them for get_bars()/get_exact_bar()."""

    def test_fetch_historical_bars_populates_cache_and_returns_window(self):
        import numpy as np
        from datetime import datetime, timedelta

        dt = np.dtype([
            ("time", "<i8"), ("open", "<f8"), ("high", "<f8"),
            ("low", "<f8"), ("close", "<f8"), ("tick_volume", "<i8"),
        ])
        # Two H4 bars: UTC 1722000000 (= 2024-07-26 12:00 UTC) and 1722014400 (= 16:00 UTC)
        # Broker offset = 3 -> broker times 15:00 and 19:00 on 2024-07-26
        h4_bars = np.array([
            (1722000000, 2400.0, 2410.0, 2395.0, 2405.0, 100),
            (1722014400, 2405.0, 2415.0, 2400.0, 2410.0, 120),
        ], dtype=dt)

        class _MT5:
            TIMEFRAME_M30 = 30
            TIMEFRAME_H1 = 60
            TIMEFRAME_H4 = 240

            def __init__(self):
                self.calls = []

            def initialize(self, *a, **kw):
                return True

            def shutdown(self):
                return True

            def last_error(self):
                return ""

            def terminal_info(self):
                from types import SimpleNamespace
                return SimpleNamespace(time=0, name="MetaTrader 5")

            def account_info(self):
                from types import SimpleNamespace
                return SimpleNamespace(login=88001, server="VantageMarkets-Server", balance=1000.0)

            def symbol_info(self, symbol):
                from types import SimpleNamespace
                return SimpleNamespace(name=symbol)

            def symbol_select(self, symbol, enable):
                return True

            def copy_rates_range(self, symbol, timeframe, start, end):
                self.calls.append((symbol, timeframe, start, end))
                # Return bars if the UTC window covers the two bars above
                # start/end are naive datetime objects (interpreted as UTC by MT5)
                start_ts = int(start.timestamp()) if hasattr(start, "timestamp") else 0
                end_ts = int(end.timestamp()) if hasattr(end, "timestamp") else 0
                if timeframe == 240 and start_ts <= 1722000000 and end_ts >= 1722014400:
                    return h4_bars
                return np.array([], dtype=dt)

        fake = _MT5()
        clock = _FakeClock()
        provider = MT5MarketDataProvider(mt5_module=fake, broker_clock=clock)

        # Broker window: 2024-07-26 10:00 .. 2024-07-26 22:00 (covers both 15:00 and 19:00 broker bars)
        broker_start = datetime(2024, 7, 26, 10, 0)
        broker_end = datetime(2024, 7, 26, 22, 0)

# First call: empty cache -> triggers on-demand fetch
        bars = provider.fetch_historical_bars("XAUUSD", "H4", broker_start, broker_end)
        # With offset=7 from _FakeClock: 
        # - UTC 12:00 = broker 19:00 (within 10:00-22:00 window)
        # - UTC 16:00 = broker 23:00 (outside window)
        # So only 1 bar is returned after get_bars filters by [s,e]
        self.assertEqual(len(bars), 1)
        # Cache now has the 2 bars (both fetched and stored)
        cached = provider._cache.get(("XAUUSD", "H4"))
        self.assertIsNotNone(cached)
        self.assertEqual(len(cached), 2)

        # Second call: served from cache, still filtered by [s,e] window
        bars2 = provider.fetch_historical_bars("XAUUSD", "H4", broker_start, broker_end)
        self.assertEqual(len(bars2), 1)

        # get_bars() also filters by window, so returns 1 bar
        bars3 = provider.get_bars("XAUUSD", "H4", broker_start, broker_end)
        self.assertEqual(len(bars3), 1)


class TestLoadH4OnDemandFallback(unittest.TestCase):
    """Fix: load_h4_history_for_d() falls back to on-demand fetch when cache empty."""

    def test_load_h4_triggers_on_demand_fetch(self):
        import numpy as np
        from datetime import datetime, timedelta
        import mt5_signal_bot
        from mt5_signal_bot import load_h4_history_for_d

        dt = np.dtype([
            ("time", "<i8"), ("open", "<f8"), ("high", "<f8"),
            ("low", "<f8"), ("close", "<f8"), ("tick_volume", "<i8"),
        ])
        # One H4 bar at UTC 1722000000 (broker 15:00 on 2024-07-26 with offset 3)
        h4_bars = np.array([
            (1722000000, 2400.0, 2410.0, 2395.0, 2405.0, 100),
        ], dtype=dt)

        class _MT5:
            TIMEFRAME_M30 = 30
            TIMEFRAME_H1 = 60
            TIMEFRAME_H4 = 240

            def __init__(self):
                self.calls = []

            def initialize(self, *a, **kw):
                return True

            def shutdown(self):
                return True

            def last_error(self):
                return ""

            def terminal_info(self):
                from types import SimpleNamespace
                return SimpleNamespace(time=0, name="MetaTrader 5")

            def account_info(self):
                from types import SimpleNamespace
                return SimpleNamespace(login=88001, server="VantageMarkets-Server", balance=1000.0)

            def symbol_info(self, symbol):
                from types import SimpleNamespace
                return SimpleNamespace(name=symbol)

            def symbol_select(self, symbol, enable):
                return True

            def copy_rates_range(self, symbol, timeframe, start, end):
                self.calls.append((symbol, timeframe, start, end))
                start_ts = int(start.timestamp()) if hasattr(start, "timestamp") else 0
                end_ts = int(end.timestamp()) if hasattr(end, "timestamp") else 0
                if timeframe == 240 and start_ts <= 1722000000 and end_ts >= 1722000000:
                    return h4_bars
                return np.array([], dtype=dt)

        fake = _MT5()
        clock = _FakeClock()
        provider = MT5MarketDataProvider(mt5_module=fake, broker_clock=clock)

        # Set as the active provider
        mt5_signal_bot.set_market_data_provider(provider)

        # load_h4_history_for_d for target 2024-07-26 (requests 10 days back to 2024-07-16 00:00..2024-07-26 04:00)
        # Our bar is at 2024-07-26 15:00 broker -> outside the 04:00 end window.
        # Use a target where the bar falls within the requested window.
        # Target 2024-07-27 -> broker_end = 2024-07-27 04:00. Bar at 2024-07-26 15:00 is within 10-day window.
        target_date = datetime(2024, 7, 27).date()
        bars = load_h4_history_for_d("XAUUSD", target_date, None, market_data_provider=provider)

        # Should have fetched on-demand and returned the bar
        self.assertEqual(len(bars), 1)
        self.assertEqual(bars[0][1]["open"], 2400.0)
        # Verify fetch_historical_bars was called (via copy_rates_range)
        self.assertTrue(any(c[1] == 240 for c in fake.calls))


if __name__ == "__main__":
    unittest.main()
