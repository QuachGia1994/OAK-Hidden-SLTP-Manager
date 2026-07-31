"""D-Direction: H4 20:00 candle from previous broker session (v82)."""

import unittest
from datetime import datetime, date, timedelta, timezone
from unittest.mock import patch, MagicMock

import numpy as np

import mt5_signal_bot

_MT5_DTYPE = [
    ("time", "<i8"), ("open", "<f8"), ("high", "<f8"),
    ("low", "<f8"), ("close", "<f8"), ("tick_volume", "<u8"),
    ("spread", "<i4"), ("real_volume", "<u8"),
]


def _make_rates(bars):
    """Create numpy structured array from list of (ts, o, h, l, c) tuples."""
    data = [(ts, o, h, l, c, 100, 5, 0) for ts, o, h, l, c in bars]
    return np.array(data, dtype=_MT5_DTYPE)


def _broker_to_utc(broker_dt, offset=3):
    """Convert broker datetime to UTC, returning timezone-aware datetime."""
    naive_utc = broker_dt - timedelta(hours=offset)
    return naive_utc.replace(tzinfo=timezone.utc)


def _utc_to_broker(utc_dt, offset=3):
    return utc_dt + timedelta(hours=offset)


def _make_h4_20_candle_rates(session_date, broker_offset=3):
    """Create H4 rates with a candle opening at broker 20:00."""
    broker_open = datetime.combine(session_date, datetime.min.time()) + timedelta(hours=20)
    utc_open = _broker_to_utc(broker_open, offset=broker_offset)
    ts = int(utc_open.timestamp())
    # TANG candle (close > open) → BUY
    return _make_rates([(ts, 2300.0, 2305.0, 2298.0, 2303.0)])


def _make_m30_session_bars(session_date, broker_offset=3):
    """Create M30 bars for a session so find_previous_available_broker_session finds it."""
    bars = []
    for hour in range(0, 24):
        for minute in (0, 30):
            broker_dt = datetime.combine(session_date, datetime.min.time()) + timedelta(hours=hour, minutes=minute)
            utc_dt = _broker_to_utc(broker_dt, offset=broker_offset)
            bars.append((int(utc_dt.timestamp()), 2300.0, 2301.0, 2299.0, 2300.5))
    return _make_rates(bars)


def _copy_rates_side_effect(session_date, broker_offset=3):
    """Return side_effect function that returns M30 or H4 rates based on timeframe."""
    m30_bars = _make_m30_session_bars(session_date, broker_offset)
    h4_bars = _make_h4_20_candle_rates(session_date, broker_offset)

    def side_effect(symbol, timeframe, start, end):
        if timeframe == mt5_signal_bot.mt5.TIMEFRAME_M30:
            return m30_bars
        elif timeframe == mt5_signal_bot.mt5.TIMEFRAME_H4:
            return h4_bars
        return None

    return side_effect


class DailyDirectionDiscoveryTests(unittest.TestCase):
    def setUp(self):
        mt5_signal_bot.clear_d_direction_cache()

    @patch("mt5_signal_bot.BROKER_CLOCK")
    @patch("mt5_signal_bot.mt5")
    def test_normal_session_finds_h4_20_candle(self, mock_mt5, mock_clock):
        """H4 20:00 candle from previous session → BUY (TANG)."""
        mock_clock.utc_offset_for_date.return_value = 3
        mock_clock.mt5_timestamp_from_broker_datetime.side_effect = lambda dt: int((dt - timedelta(hours=3)).replace(tzinfo=timezone.utc).timestamp())
        mock_clock.broker_datetime_from_mt5_timestamp.side_effect = lambda ts: datetime.fromtimestamp(ts, tz=timezone.utc).replace(tzinfo=None) + timedelta(hours=3)
        mock_mt5.symbol_select.return_value = True
        mock_mt5.TIMEFRAME_M30 = 16385
        mock_mt5.TIMEFRAME_H4 = 16408

        session_date = date(2026, 7, 29)
        mock_mt5.copy_rates_range.side_effect = _copy_rates_side_effect(session_date, broker_offset=3)

        result = mt5_signal_bot.calculate_d_direction("XAUUSD", date(2026, 7, 30))
        # XAUUSD uses GBPUSD as source → D-Direction comes from GBPUSD H4 20:00
        self.assertEqual(result["d_direction"], "BUY")
        self.assertEqual(result["d_state"], "READY")
        self.assertEqual(result["source_symbol"], "GBPUSD")
        self.assertEqual(result["timeframe"], "H4")

    @patch("mt5_signal_bot.BROKER_CLOCK")
    @patch("mt5_signal_bot.mt5")
    def test_missing_data_returns_wait(self, mock_mt5, mock_clock):
        mock_clock.utc_offset_for_date.return_value = 3
        mock_mt5.symbol_select.return_value = True
        mock_mt5.TIMEFRAME_M30 = 16385
        mock_mt5.TIMEFRAME_H4 = 16408
        mock_mt5.copy_rates_range.return_value = None

        result = mt5_signal_bot.calculate_d_direction("XAUUSD", date(2026, 7, 30))
        self.assertEqual(result["d_direction"], "WAIT")
        self.assertIn(result["d_state"], ("MISSING", "MISSING_H4_20"))

    @patch("mt5_signal_bot.BROKER_CLOCK")
    @patch("mt5_signal_bot.mt5")
    def test_missing_h4_20_candle_returns_wait(self, mock_mt5, mock_clock):
        """If session exists but H4 20:00 candle is missing → WAIT (MISSING_H4_20)."""
        mock_clock.utc_offset_for_date.return_value = 3
        mock_mt5.symbol_select.return_value = True
        mock_mt5.TIMEFRAME_M30 = 16385
        mock_mt5.TIMEFRAME_H4 = 16408

        session_date = date(2026, 7, 29)
        m30_bars = _make_m30_session_bars(session_date, broker_offset=3)
        # H4 rates with no 20:00 candle (only 16:00 candle)
        broker_open_16 = datetime.combine(session_date, datetime.min.time()) + timedelta(hours=16)
        utc_open_16 = _broker_to_utc(broker_open_16, offset=3)
        h4_bars_no_20 = _make_rates([(int(utc_open_16.timestamp()), 2300.0, 2305.0, 2298.0, 2303.0)])

        def side_effect(symbol, timeframe, start, end):
            if timeframe == mt5_signal_bot.mt5.TIMEFRAME_M30:
                return m30_bars
            elif timeframe == mt5_signal_bot.mt5.TIMEFRAME_H4:
                return h4_bars_no_20
            return None

        mock_mt5.copy_rates_range.side_effect = side_effect

        result = mt5_signal_bot.calculate_d_direction("GBPUSD", date(2026, 7, 30))
        self.assertEqual(result["d_direction"], "WAIT")
        self.assertEqual(result["failure_reason"], "MISSING_H4_20")

    @patch("mt5_signal_bot.BROKER_CLOCK")
    @patch("mt5_signal_bot.mt5")
    def test_per_symbol_independence(self, mock_mt5, mock_clock):
        """Each symbol gets its own D-Direction."""
        mock_clock.utc_offset_for_date.return_value = 3
        mock_mt5.symbol_select.return_value = True
        mock_mt5.TIMEFRAME_M30 = 16385
        mock_mt5.TIMEFRAME_H4 = 16408
        mock_mt5.copy_rates_range.return_value = None

        results = mt5_signal_bot.calculate_all_d_directions(date(2026, 7, 30))
        self.assertEqual(len(results), 5)
        for sym in mt5_signal_bot.D_DIRECTION_PAIRS:
            self.assertIn(sym, results)
            self.assertEqual(results[sym]["symbol"], sym)

    def test_cache_prevents_recalculation(self):
        """Same (date, symbol) returns cached result."""
        mt5_signal_bot._d_direction_cache[("2026-07-30", "XAUUSD")] = {
            "symbol": "XAUUSD", "d_direction": "BUY", "d_state": "READY",
            "source_symbol": "GBPUSD", "timeframe": "H4",
        }
        result = mt5_signal_bot.calculate_d_direction("XAUUSD", date(2026, 7, 30))
        self.assertEqual(result["d_direction"], "BUY")

    @patch("mt5_signal_bot.BROKER_CLOCK")
    @patch("mt5_signal_bot.mt5")
    def test_xauusd_uses_gbpusd_source(self, mock_mt5, mock_clock):
        """XAUUSD D-Direction uses GBPUSD as source symbol."""
        mock_clock.utc_offset_for_date.return_value = 3
        mock_mt5.symbol_select.return_value = True
        mock_mt5.TIMEFRAME_M30 = 16385
        mock_mt5.TIMEFRAME_H4 = 16408

        session_date = date(2026, 7, 29)
        mock_mt5.copy_rates_range.side_effect = _copy_rates_side_effect(session_date, broker_offset=3)

        result = mt5_signal_bot.calculate_d_direction("XAUUSD", date(2026, 7, 30))
        self.assertEqual(result["source_symbol"], "GBPUSD")
        self.assertEqual(result["symbol"], "XAUUSD")


class DailyDirectionPairIndependenceTests(unittest.TestCase):
    def setUp(self):
        mt5_signal_bot.clear_d_direction_cache()

    @patch("mt5_signal_bot.BROKER_CLOCK")
    @patch("mt5_signal_bot.mt5")
    def test_five_symbols_calculated_independently(self, mock_mt5, mock_clock):
        mock_clock.utc_offset_for_date.return_value = 3
        mock_mt5.symbol_select.return_value = True
        mock_mt5.TIMEFRAME_M30 = 16385
        mock_mt5.TIMEFRAME_H4 = 16408
        mock_mt5.copy_rates_range.return_value = None

        results = mt5_signal_bot.calculate_all_d_directions(date(2026, 7, 30))
        self.assertEqual(set(results.keys()), set(mt5_signal_bot.D_DIRECTION_PAIRS))
        # GBPJPY and GBPCAD are in D_DIRECTION_PAIRS even though they're disabled for signals
        self.assertIn("GBPJPY", results)
        self.assertIn("GBPCAD", results)


if __name__ == "__main__":
    unittest.main()
