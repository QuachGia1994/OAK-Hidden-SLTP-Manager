"""Week-open market closure: Monday slots whose M30 inputs predate the broker's
first bar of the week are valid WAITs (MARKET_CLOSED_WEEK_OPEN), never missing
inputs — while unprovable closures (no bars at all) and mid-week misses keep
the MISSING tag so genuine outages are never masked.

Regression context: brokers like Vantage open the trading week Monday 03:00
Broker (00:00 UTC), so H3's M30 layer candles (01:30/02:00/02:30 Broker) never
exist on Mondays.  Every Monday rebuild was forced REBUILD_INCOMPLETE until
those misses were reclassified as scheduled market closures.
"""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import mt5_signal_bot

MONDAY = datetime(2026, 8, 3)   # weekday() == 0
TUESDAY = datetime(2026, 8, 4)


def _bar(broker_dt):
    return {
        "time": int(broker_dt.timestamp()),
        "open": 1.0,
        "high": 1.0,
        "low": 1.0,
        "close": 1.0,
        "broker_dt": broker_dt,
        "is_complete": True,
    }


class WeekOpenProvider:
    """Serves XAUUSD M30 bars for one broker date starting at ``first_open``."""

    name = "MT5"

    def __init__(self, target_date, first_open=None):
        self._target_date = target_date
        self._first_open = first_open

    def get_bars(self, symbol, timeframe, start_broker, end_broker):
        if symbol != "XAUUSD" or str(timeframe).upper() != "M30" or self._first_open is None:
            return []
        day_end = datetime.combine(self._target_date, datetime.min.time()) + timedelta(days=1)
        bars = []
        cursor = self._first_open
        while cursor < day_end:
            bars.append(_bar(cursor))
            cursor += timedelta(minutes=30)
        return [b for b in bars if start_broker <= b["broker_dt"] <= end_broker]


def _missing_reasons():
    return {
        "XAUUSD": "M30_LAYER2_MISSING",
        "GBPUSD": "M30_LAYER2_MISSING",
        "GBPAUD": "M30_LAYER3_MISSING",
        "GBPJPY": "M30_LAYER3_MISSING",
        "GBPCAD": "NOT_APPLICABLE",
    }


class ReclassifyWeekOpenTests(unittest.TestCase):
    def test_monday_misses_predating_week_open_become_market_closed(self):
        provider = WeekOpenProvider(MONDAY.date(), first_open=datetime(2026, 8, 3, 3))
        reasons = mt5_signal_bot._reclassify_week_open_market_closed(
            _missing_reasons(), MONDAY.replace(hour=3), 3, provider=provider
        )
        for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY"):
            self.assertEqual(reasons[symbol], "MARKET_CLOSED_WEEK_OPEN", symbol)
        self.assertEqual(reasons["GBPCAD"], "NOT_APPLICABLE")

    def test_tuesday_misses_stay_missing(self):
        provider = WeekOpenProvider(TUESDAY.date(), first_open=datetime(2026, 8, 4, 0))
        original = _missing_reasons()
        reasons = mt5_signal_bot._reclassify_week_open_market_closed(
            dict(original), TUESDAY.replace(hour=3), 3, provider=provider
        )
        self.assertEqual(reasons, original)

    def test_monday_without_any_bars_stays_missing(self):
        # No bar at all cannot prove a scheduled closure (could be an outage).
        provider = WeekOpenProvider(MONDAY.date(), first_open=None)
        original = _missing_reasons()
        reasons = mt5_signal_bot._reclassify_week_open_market_closed(
            dict(original), MONDAY.replace(hour=3), 3, provider=provider
        )
        self.assertEqual(reasons, original)

    def test_monday_first_bar_before_slot_stays_missing(self):
        # Market opened 01:00 but a required 01:30/02:00 candle is absent: a
        # genuine intra-session gap, not the week-open closure.
        provider = WeekOpenProvider(MONDAY.date(), first_open=datetime(2026, 8, 3, 1))
        original = _missing_reasons()
        reasons = mt5_signal_bot._reclassify_week_open_market_closed(
            dict(original), MONDAY.replace(hour=3), 3, provider=provider
        )
        self.assertEqual(reasons, original)

    def test_non_m30_reasons_untouched(self):
        provider = WeekOpenProvider(MONDAY.date(), first_open=datetime(2026, 8, 3, 3))
        original = {"XAUUSD": "D_H4_MISSING", "GBPUSD": "H49_H1_DOJI"}
        reasons = mt5_signal_bot._reclassify_week_open_market_closed(
            dict(original), MONDAY.replace(hour=3), 3, provider=provider
        )
        self.assertEqual(reasons, original)


class WeekOpenTaxonomyTests(unittest.TestCase):
    def test_reason_is_valid_not_missing(self):
        self.assertIn("MARKET_CLOSED_WEEK_OPEN", mt5_signal_bot.VALID_WAIT_REASONS)
        self.assertNotIn("MARKET_CLOSED_WEEK_OPEN", mt5_signal_bot.MISSING_INPUT_WAIT_REASONS)

    def test_rebuild_complete_accepts_market_closed_waits(self):
        record = {
            "rebuild_state": "READY",
            "pair_signal_states": {"XAUUSD": "WAIT", "GBPUSD": "WAIT", "GBPCAD": "NOT_APPLICABLE"},
            "wait_reasons": {
                "XAUUSD": "MARKET_CLOSED_WEEK_OPEN",
                "GBPUSD": "MARKET_CLOSED_WEEK_OPEN",
                "GBPCAD": "NOT_APPLICABLE",
            },
        }
        self.assertTrue(mt5_signal_bot._compute_rebuild_complete([record]))


def _missing_layer_result():
    """Minimal v88 eval result whose entry layers report MISSING M30 candles."""
    return {
        "signal": "WAIT",
        "signal_state": "WAIT",
        "entry_state": "WAIT",
        "entry_time": None,
        "source_date": "2026-08-03",
        "pair_dirs": {symbol: "WAIT" for symbol in mt5_signal_bot.SIGNAL_PAIRS},
        "pair_signal_states": {
            "XAUUSD": "WAIT",
            "GBPUSD": "WAIT",
            "GBPAUD": "WAIT",
            "GBPJPY": "WAIT",
            "GBPCAD": "NOT_APPLICABLE",
        },
        "applicable_pairs": ["XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY"],
        "pair_evidence": {},
        "timing": {
            "layers": {
                "layer2": {"candles": [{"state": "MISSING"}], "group": "A"},
                "layer3": {"candles": [{"state": "OK"}], "group": "A"},
            }
        },
        "_pair_day_modes_objects": {symbol: None for symbol in mt5_signal_bot.SIGNAL_PAIRS},
    }


class WeekOpenRebuildRecordTests(unittest.TestCase):
    def test_monday_h3_record_is_market_closed_not_missing_input(self):
        provider = WeekOpenProvider(MONDAY.date(), first_open=datetime(2026, 8, 3, 3))
        with (
            patch.object(mt5_signal_bot, "MARKET_DATA_PROVIDER", provider),
            patch.object(mt5_signal_bot, "evaluate_all_pairs_for_slot", return_value=_missing_layer_result()),
            patch.object(mt5_signal_bot, "get_current_prices", return_value={}),
        ):
            record, _ = mt5_signal_bot._build_rebuild_record(MONDAY.replace(hour=3), 3)

        reasons = record["wait_reasons"]
        for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY"):
            self.assertEqual(reasons[symbol], "MARKET_CLOSED_WEEK_OPEN", symbol)
        self.assertEqual(reasons["GBPCAD"], "NOT_APPLICABLE")
        self.assertEqual(mt5_signal_bot._missing_inputs_for_record(record), [])
        self.assertNotEqual(record.get("rebuild_state"), "MISSING_INPUT")
        self.assertTrue(mt5_signal_bot._compute_rebuild_complete([record]))

    def test_monday_h3_record_without_bars_stays_missing_input(self):
        provider = WeekOpenProvider(MONDAY.date(), first_open=None)
        with (
            patch.object(mt5_signal_bot, "MARKET_DATA_PROVIDER", provider),
            patch.object(mt5_signal_bot, "evaluate_all_pairs_for_slot", return_value=_missing_layer_result()),
            patch.object(mt5_signal_bot, "get_current_prices", return_value={}),
        ):
            record, _ = mt5_signal_bot._build_rebuild_record(MONDAY.replace(hour=3), 3)

        self.assertEqual(record["wait_reasons"]["XAUUSD"], "M30_LAYER2_MISSING")
        self.assertEqual(record.get("rebuild_state"), "MISSING_INPUT")
        self.assertFalse(mt5_signal_bot._compute_rebuild_complete([record]))


if __name__ == "__main__":
    unittest.main()
