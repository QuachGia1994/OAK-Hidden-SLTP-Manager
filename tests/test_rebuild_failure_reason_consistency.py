"""Regression: a Monday week-open rebuild whose per-pair wait_reasons were
reclassified as MARKET_CLOSED_WEEK_OPEN (a valid WAIT) must never keep a stale
record-level missing-input failure_reason such as WAIT_MT5_DATA.

Before the fix the record-level failure_reason was copied from the evaluator
result and never re-derived after _reclassify_week_open_market_closed, so the
dashboard integrity gate flagged these valid Monday WAITs as "THIẾU NGUỒN".
"""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from mt4_feed_test_environment import install_isolated_mt4_feed_database

install_isolated_mt4_feed_database()

import mt5_signal_bot

MONDAY = datetime(2026, 8, 3)   # weekday() == 0


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


def _missing_layer_result_with_stale_failure():
    """v88 eval result with missing M30 candles AND a stale record-level
    WAIT_MT5_DATA failure_reason (the shape the real evaluator emits)."""
    return {
        "signal": "WAIT",
        "signal_state": "WAIT",
        "entry_state": "WAIT",
        "entry_time": None,
        "source_date": "2026-08-03",
        "failure_reason": "WAIT_MT5_DATA",
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


class WeekOpenRebuildFailureReasonTests(unittest.TestCase):
    def test_monday_week_open_record_clears_stale_failure_reason(self):
        provider = WeekOpenProvider(MONDAY.date(), first_open=datetime(2026, 8, 3, 3))
        with (
            patch.object(mt5_signal_bot, "MARKET_DATA_PROVIDER", provider),
            patch.object(
                mt5_signal_bot,
                "evaluate_all_pairs_for_slot",
                return_value=_missing_layer_result_with_stale_failure(),
            ),
            patch.object(mt5_signal_bot, "get_current_prices", return_value={}),
        ):
            record, _ = mt5_signal_bot._build_rebuild_record(MONDAY.replace(hour=3), 3)

        for symbol in ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY"):
            self.assertEqual(record["wait_reasons"][symbol], "MARKET_CLOSED_WEEK_OPEN", symbol)
        self.assertEqual(record["wait_reasons"]["GBPCAD"], "NOT_APPLICABLE")
        self.assertEqual(mt5_signal_bot._missing_inputs_for_record(record), [])
        self.assertIsNone(record.get("failure_reason"))
        self.assertNotIn(
            record.get("rebuild_state"), ("MISSING_INPUT", "REBUILD_INCOMPLETE")
        )
        self.assertTrue(mt5_signal_bot._compute_rebuild_complete([record]))

    def test_genuine_missing_record_keeps_failure_reason(self):
        # No bars at all: the M30 misses stay M30_LAYER2_MISSING and the
        # record-level failure_reason must be preserved.
        provider = WeekOpenProvider(MONDAY.date(), first_open=None)
        with (
            patch.object(mt5_signal_bot, "MARKET_DATA_PROVIDER", provider),
            patch.object(
                mt5_signal_bot,
                "evaluate_all_pairs_for_slot",
                return_value=_missing_layer_result_with_stale_failure(),
            ),
            patch.object(mt5_signal_bot, "get_current_prices", return_value={}),
        ):
            record, _ = mt5_signal_bot._build_rebuild_record(MONDAY.replace(hour=3), 3)

        self.assertEqual(record["wait_reasons"]["XAUUSD"], "M30_LAYER2_MISSING")
        self.assertEqual(record.get("failure_reason"), "WAIT_MT5_DATA")
        self.assertEqual(record.get("rebuild_state"), "MISSING_INPUT")
        self.assertFalse(mt5_signal_bot._compute_rebuild_complete([record]))


if __name__ == "__main__":
    unittest.main()
