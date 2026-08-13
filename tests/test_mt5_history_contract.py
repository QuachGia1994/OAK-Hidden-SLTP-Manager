"""Current MT5 history-provider and rebuild-worker contracts."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import unittest

import mt5_signal_bot
from history_rebuild_worker import HistoryRebuildWorker
from providers.mt5_market_data_provider import MT5MarketDataProvider
from test_feed_coverage import FakeMT5, FixedClock


def _rate(broker_dt, open_value, close_value):
    utc_dt = (broker_dt - timedelta(hours=3)).replace(tzinfo=timezone.utc)
    return {
        "time": int(utc_dt.timestamp()),
        "open": float(open_value),
        "high": max(float(open_value), float(close_value)) + 1,
        "low": min(float(open_value), float(close_value)) - 1,
        "close": float(close_value),
        "tick_volume": 10,
    }


class HistoryMT5(FakeMT5):
    def __init__(self, rates):
        super().__init__()
        self._rates = {"XAUUSD": list(rates)}


def _provider(rates):
    provider = MT5MarketDataProvider(mt5_module=HistoryMT5(rates), broker_clock=FixedClock())
    provider.bind_profile({"login_id": 12345, "server": "VantageMarkets-Live 3"})
    assert provider.connect()
    return provider


class MT5HistoryProviderTests(unittest.TestCase):
    def test_h4_anchor_comes_from_current_mt5_provider(self):
        target = datetime(2026, 8, 3)
        session = datetime(2026, 8, 2, 20)
        provider = _provider([_rate(session, 2400, 2405), _rate(datetime(2026, 8, 1, 20), 2390, 2395)])

        with patch.object(mt5_signal_bot, "BROKER_CLOCK", FixedClock()):
            candle, selected, offset, ambiguous = mt5_signal_bot.find_previous_session_h4_20_candle(
                "XAUUSD", target.date(), market_data_provider=provider
            )

        self.assertEqual(selected, session.date())
        self.assertEqual(offset, 3)
        self.assertFalse(ambiguous)
        self.assertEqual(candle["open_exact"], "2400.000000")
        self.assertEqual(candle["close_exact"], "2405.000000")

    def test_h4_grid_does_not_promote_off_grid_21h_bar(self):
        target = datetime(2026, 8, 3)
        rates = [
            _rate(datetime(2026, 8, 1, 20), 2390, 2395),
            _rate(datetime(2026, 7, 31, 20), 2380, 2385),
            _rate(datetime(2026, 8, 2, 21), 2400, 2410),
        ]
        provider = _provider(rates)

        with patch.object(mt5_signal_bot, "BROKER_CLOCK", FixedClock()):
            candle, selected, _offset, ambiguous = mt5_signal_bot.find_previous_session_h4_20_candle(
                "XAUUSD", target.date(), market_data_provider=provider
            )

        self.assertFalse(ambiguous)
        self.assertNotEqual(selected, datetime(2026, 8, 2).date())
        self.assertNotEqual(candle["broker_dt"].hour, 21)


class WatermarkStore:
    def __init__(self, latest):
        self.latest = latest

    def get_latest_bar_received_at(self):
        return self.latest


class HistoryRebuildWorkerTests(unittest.TestCase):
    def test_worker_runs_when_mt5_persisted_bar_watermark_changes(self):
        store = WatermarkStore(datetime(2026, 8, 13, 5))
        calls = []
        worker = HistoryRebuildWorker(store=store, rebuild_fn=lambda days: calls.append(days), days=45)

        self.assertTrue(worker.should_run())
        self.assertTrue(worker.run_once())
        self.assertEqual(calls, [45])
        self.assertFalse(worker.should_run())

    def test_worker_records_incomplete_mt5_rebuild_without_false_success(self):
        store = WatermarkStore(datetime(2026, 8, 13, 5))
        previous = mt5_signal_bot._LAST_REBUILD_COMPLETE

        def incomplete_rebuild(days):
            mt5_signal_bot._LAST_REBUILD_COMPLETE = False

        try:
            worker = HistoryRebuildWorker(store=store, rebuild_fn=incomplete_rebuild)
            mt5_signal_bot._LAST_REBUILD_COMPLETE = True
            self.assertTrue(worker.run_once())
            self.assertFalse(worker._last_rebuild_complete)
        finally:
            mt5_signal_bot._LAST_REBUILD_COMPLETE = previous


if __name__ == "__main__":
    unittest.main()
