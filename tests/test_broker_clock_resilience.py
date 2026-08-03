"""Regression tests for broker clock resilience against transient failures.

Covers four defensive layers added to keep the dashboard from flapping to
"ĐANG CHỜ" / "CHƯA ĐỒNG BỘ" / "THIẾU NGUỒN" when the broker clock or the
M30 layer source isn't immediately available:

1. ``MT5MarketDataProvider.get_broker_utc_offset`` falls through to
   ``current_utc_offset`` (which has its own cache fallback) when
   ``utc_offset_for_date`` raises, so a single tick stall or D1 timeout no
   longer voids the published offset.
2. ``MT5MarketDataProvider.get_exact_bar`` attempts one on-demand
   ``fetch_historical_bars`` call on cache miss, so M30 Layer candles that
   closed after the startup preload no longer report ``M30_LAYER2_MISSING``.
3. ``mt5_signal_bot._save_state`` reuses the previously published
   broker_utc_offset when the live lookup transiently fails for the same
   broker date, instead of writing an empty clock into ``bot_state.json``.
4. ``mt5_signal_bot.publish_heartbeat`` passes ``preserve_broker_clock=True``
   and ``None`` placeholders (never empty strings) so SQLite replays the
   last good broker clock snapshot when the live heartbeat sample fails.
"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot
from providers.mt5_market_data_provider import MT5MarketDataProvider, BrokerClockError


class _RaisingOffsetClock:
    """FakeBrokerClock whose ``utc_offset_for_date`` always raises.

    ``current_utc_offset`` mirrors the real BrokerClock cache-fallback path:
    it returns a stored offset for "today" regardless of live calibration.
    """

    def __init__(self, today_offset: int, today_broker_date):
        self._today_offset = today_offset
        self._today_broker_date = today_broker_date

    def utc_offset_for_date(self, broker_date):
        raise BrokerClockError(
            f"no verified Broker offset for {broker_date.isoformat()}"
        )

    def current_utc_offset(self, now_utc=None):
        return self._today_offset

    def broker_from_utc_datetime(self, utc_datetime):  # pragma: no cover - unused
        return utc_datetime

    def is_broker_utc_offset_verified(self, broker_date=None):
        return broker_date == self._today_broker_date


class GetBrokerUtcOffsetFallbackTests(unittest.TestCase):
    def test_falls_back_to_current_utc_offset_when_utc_offset_for_date_raises(self):
        today = datetime.now(timezone.utc).date()
        clock = _RaisingOffsetClock(today_offset=3, today_broker_date=today)
        provider = MT5MarketDataProvider(mt5_module=MagicMock(), broker_clock=clock)
        broker_today_offset = provider.get_broker_utc_offset(today)
        self.assertEqual(broker_today_offset, 3)

    def test_does_not_substitute_today_offset_for_a_different_broker_date(self):
        today = datetime.now(timezone.utc).date()
        clock = _RaisingOffsetClock(today_offset=3, today_broker_date=today)
        provider = MT5MarketDataProvider(mt5_module=MagicMock(), broker_clock=clock)
        historical_date = today.replace(year=today.year - 1)
        with self.assertRaises(BrokerClockError):
            provider.get_broker_utc_offset(historical_date)


class GetExactBarAutoFetchTests(unittest.TestCase):
    def test_cache_miss_triggers_fetch_historical_bars_then_returns_bar(self):
        provider = MT5MarketDataProvider(mt5_module=MagicMock(), broker_clock=None)
        provider._connected = True
        broker_open = datetime(2026, 8, 3, 2, 30)
        bar = {
            "time": int((broker_open - datetime(1970, 1, 1)).total_seconds()),
            "broker_dt": broker_open,
            "open": 1.0,
            "high": 1.5,
            "low": 0.5,
            "close": 1.25,
            "open_exact": "1.00000",
            "high_exact": "1.50000",
            "low_exact": "0.50000",
            "close_exact": "1.25000",
            "tick_volume": 100,
            "is_complete": True,
        }

        def fake_fetch(symbol, tf, start, end, timeout_seconds=None):
            provider._cache[(symbol, str(tf).upper())] = [bar]
            return [bar]

        with patch.object(
            provider, "fetch_historical_bars", side_effect=fake_fetch
        ) as fetch_mock:
            result = provider.get_exact_bar("XAUUSD", "M30", broker_open)

        self.assertIsNotNone(result)
        self.assertEqual(result["broker_dt"], broker_open)
        fetch_mock.assert_called_once()
        args, _ = fetch_mock.call_args
        self.assertEqual(args[0], "XAUUSD")
        self.assertEqual(args[1], "M30")

    def test_skip_fetch_when_disconnected(self):
        provider = MT5MarketDataProvider(mt5_module=MagicMock(), broker_clock=None)
        provider._connected = False
        with patch.object(
            provider, "fetch_historical_bars"
        ) as fetch_mock:
            result = provider.get_exact_bar("XAUUSD", "M30", datetime(2026, 8, 3, 2, 30))
        self.assertIsNone(result)
        fetch_mock.assert_not_called()

    def test_offline_rebuild_with_source_id_skips_auto_fetch(self):
        provider = MT5MarketDataProvider(mt5_module=MagicMock(), broker_clock=None)
        provider._connected = True
        with patch.object(
            provider, "fetch_historical_bars"
        ) as fetch_mock:
            result = provider.get_exact_bar(
                "XAUUSD", "M30", datetime(2026, 8, 3, 2, 30), source_id="mt4-feed-1"
            )
        self.assertIsNone(result)
        fetch_mock.assert_not_called()


class SaveStatePreservesBrokerOffsetTests(unittest.TestCase):
    def setUp(self):
        self._tmp_dir = tempfile.mkdtemp(prefix="robot-sltp-resilience-tests-")
        self._state_path = os.path.join(self._tmp_dir, "bot_state.json")
        self._original_state_file = mt5_signal_bot._STATE_FILE
        mt5_signal_bot._STATE_FILE = self._state_path

    def tearDown(self):
        mt5_signal_bot._STATE_FILE = self._original_state_file
        for path in list(os.listdir(self._tmp_dir)):
            os.unlink(os.path.join(self._tmp_dir, path))
        os.rmdir(self._tmp_dir)

    def _write_state(self, date_str, broker_utc_offset):
        with open(self._state_path, "w", encoding="utf-8") as fh:
            json.dump(
                {
                    "date": date_str,
                    "signal_logic_version": mt5_signal_bot.SIGNAL_LOGIC_VERSION,
                    "sent_today": [],
                    "broker_time": f"{date_str}T10:00:00",
                    "broker_utc_offset": broker_utc_offset,
                    "broker_observed_at_utc": "2026-08-03T07:00:00+00:00",
                },
                fh,
            )

    def test_preserves_prior_offset_when_live_lookup_transiently_fails(self):
        broker_now = datetime(2026, 8, 3, 10, 0, 0)
        today_str = broker_now.date().isoformat()
        self._write_state(today_str, 3)

        fake_provider = MagicMock()
        fake_provider.get_broker_utc_offset.side_effect = BrokerClockError(
            "BROKER_OFFSET_UNVERIFIED: no historical offset (DST boundary)"
        )
        # ``get_broker_time`` itself succeeds (broker_dt was sampled), so its
        # underlying calls (``get_health`` + ``get_broker_now``) must too.
        fake_provider.get_health.return_value = SimpleNamespace(
            state="connected",
            fresh=True,
            degraded=False,
            age_seconds=0.0,
            observed_at_utc="2026-08-03T07:00:00+00:00",
            clock_verified=True,
        )
        fake_provider.get_broker_now.return_value = broker_now
        fake_provider.name = "MT5"

        with patch.object(mt5_signal_bot, "MARKET_DATA_PROVIDER", fake_provider):
            ok = mt5_signal_bot._save_state(set(), broker_dt=broker_now)

        self.assertTrue(ok)
        with open(self._state_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual(data["broker_utc_offset"], 3)
        self.assertEqual(data["date"], today_str)
        self.assertNotEqual(data["broker_time"], "")
        self.assertNotEqual(data["broker_observed_at_utc"], "")

    def test_does_not_substitute_prior_offset_across_different_broker_date(self):
        broker_now = datetime(2026, 8, 3, 10, 0, 0)
        today_str = broker_now.date().isoformat()
        # Prior state is for a different broker date.
        self._write_state("2026-08-02", 3)

        fake_provider = MagicMock()
        fake_provider.get_broker_utc_offset.side_effect = BrokerClockError(
            "BROKER_OFFSET_UNVERIFIED"
        )
        fake_provider.get_health.return_value = SimpleNamespace(
            state="connected",
            fresh=True,
            degraded=False,
            age_seconds=0.0,
            observed_at_utc="2026-08-03T07:00:00+00:00",
            clock_verified=True,
        )
        fake_provider.get_broker_now.return_value = broker_now
        fake_provider.name = "MT5"

        with patch.object(mt5_signal_bot, "MARKET_DATA_PROVIDER", fake_provider):
            ok = mt5_signal_bot._save_state(set(), broker_dt=broker_now)

        self.assertTrue(ok)
        with open(self._state_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertIsNone(data["broker_utc_offset"])
        self.assertEqual(data["broker_time"], "")
        self.assertEqual(data["broker_observed_at_utc"], "")


class PublishHeartbeatPreservesClockTests(unittest.TestCase):
    def test_passes_preserve_broker_clock_true_when_broker_dt_is_none(self):
        store_mock = MagicMock()
        with patch.object(mt5_signal_bot, "_store", store_mock):
            with patch.object(mt5_signal_bot, "MARKET_DATA_PROVIDER") as provider_mock:
                provider_mock.get_health.return_value = SimpleNamespace(
                    state="disconnected", observed_at_utc=""
                )
                provider_mock.name = "MT5"
                provider_mock.get_broker_utc_offset.return_value = 3
                # Force Telegram probes off so we don't depend on network.
                mt5_signal_bot._tg_probe_key = None
                mt5_signal_bot.publish_heartbeat(
                    "test-profile",
                    mt5_connected=False,
                    mt5_error="broker clock transient fail",
                    broker_dt=None,
                )

        # Last positional/keyword arg to publish_heartbeat is preserve_broker_clock=True
        kwargs = store_mock.publish_heartbeat.call_args.kwargs
        self.assertIs(kwargs["preserve_broker_clock"], True)
        self.assertIsNone(kwargs["broker_time"])
        self.assertIsNone(kwargs["broker_utc_offset"])
        self.assertIsNone(kwargs["broker_observed_at_utc"])

    def test_publishes_fresh_clock_fields_when_broker_dt_and_offset_resolve(self):
        store_mock = MagicMock()
        broker_dt = datetime(2026, 8, 3, 10, 0, 0)
        with patch.object(mt5_signal_bot, "_store", store_mock):
            with patch.object(mt5_signal_bot, "MARKET_DATA_PROVIDER") as provider_mock:
                provider_mock.get_health.return_value = SimpleNamespace(
                    state="connected", observed_at_utc="2026-08-03T07:00:00+00:00"
                )
                provider_mock.name = "MT5"
                provider_mock.get_broker_utc_offset.return_value = 3
                mt5_signal_bot._tg_probe_key = None
                mt5_signal_bot.publish_heartbeat(
                    "test-profile",
                    mt5_connected=True,
                    broker_dt=broker_dt,
                )

        kwargs = store_mock.publish_heartbeat.call_args.kwargs
        self.assertTrue(kwargs["preserve_broker_clock"])
        self.assertEqual(kwargs["broker_time"], "2026-08-03T10:00:00")
        self.assertEqual(kwargs["broker_utc_offset"], 3)
        self.assertEqual(kwargs["broker_observed_at_utc"], "2026-08-03T07:00:00+00:00")


if __name__ == "__main__":
    unittest.main()