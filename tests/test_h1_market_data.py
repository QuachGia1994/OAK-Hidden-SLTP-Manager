from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

APP = Path(__file__).resolve().parents[1] / "robot-sltp-pro"
sys.path.insert(0, str(APP))

from ctrader_h1_market_data import h1_rows_to_server_wall
from h1_market_data import (
    build_h1_snapshot_payload,
    candle_direction,
    compare_h1_candles,
    icmarkets_server_offset_seconds,
    icmarkets_server_wall_epoch,
    parse_h1_snapshot,
    scanner_relevant_h1,
)
from market_data_provider import Candle


def epoch(year: int, month: int, day: int, hour: int) -> int:
    return int(datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp())


def trendbar(ts_minutes: int, low: int, delta_open: int, delta_high: int, delta_close: int):
    return SimpleNamespace(
        utcTimestampInMinutes=ts_minutes,
        low=low,
        deltaOpen=delta_open,
        deltaHigh=delta_high,
        deltaClose=delta_close,
    )


def test_h1_direction_uses_close_strictly_above_open_and_doji_is_g():
    assert candle_direction(Candle(1, 1.0, 1.2, 0.9, 1.1)) == "T"
    assert candle_direction(Candle(2, 1.0, 1.1, 0.9, 1.0)) == "G"
    assert candle_direction(Candle(3, 1.0, 1.1, 0.8, 0.9)) == "G"


def test_icmarkets_server_wall_normalization_matches_mt5_hour_encoding():
    assert icmarkets_server_offset_seconds(epoch(2026, 1, 15, 22)) == 2 * 3600
    assert icmarkets_server_offset_seconds(epoch(2026, 8, 20, 21)) == 3 * 3600
    assert icmarkets_server_wall_epoch(epoch(2026, 1, 15, 22)) == epoch(2026, 1, 16, 0)
    assert icmarkets_server_wall_epoch(epoch(2026, 8, 20, 21)) == epoch(2026, 8, 21, 0)


def test_ctrader_h1_rows_are_kept_as_h1_and_only_timestamp_is_normalized():
    utc = epoch(2026, 8, 20, 21)
    rows = h1_rows_to_server_wall((trendbar(utc // 60, 110000, 20, 80, 50),), 5)
    assert rows == (Candle(epoch(2026, 8, 21, 0), 1.1002, 1.1008, 1.1, 1.1005),)


def test_snapshot_filters_one_broker_day_and_round_trips():
    candles = {
        "GBPUSD": (
            Candle(epoch(2026, 8, 20, 23), 1.0, 1.2, 0.9, 1.1),
            Candle(epoch(2026, 8, 21, 0), 1.1, 1.3, 1.0, 1.2),
            Candle(epoch(2026, 8, 21, 1), 1.2, 1.3, 1.1, 1.15),
        )
    }
    payload = build_h1_snapshot_payload(provider="test", candles_by_symbol=candles, broker_date="2026-08-21")
    assert payload["timeframe"] == "H1"
    assert payload["brokerDate"] == "2026-08-21"
    assert [row["direction"] for row in payload["candles"]["GBPUSD"]] == ["T", "G"]
    restored = parse_h1_snapshot(payload)
    assert [row.time for row in restored["GBPUSD"]] == [epoch(2026, 8, 21, 0), epoch(2026, 8, 21, 1)]


def test_scanner_relevant_h1_excludes_h00_and_h17_plus():
    rows = tuple(
        Candle(epoch(2026, 8, 21, hour), 1.0, 1.2, 0.9, 1.1)
        for hour in (0, 1, 16, 17, 23)
    )
    assert [datetime.fromtimestamp(row.time, tz=timezone.utc).hour for row in scanner_relevant_h1(rows)] == [1, 16]


def test_h1_parity_passes_when_scanner_direction_matches_even_if_ohlc_differs():
    times = [epoch(2026, 8, 21, 0), epoch(2026, 8, 21, 1)]
    baseline = (
        Candle(times[0], 1.1000, 1.1010, 1.0990, 1.1005),
        Candle(times[1], 1.1005, 1.1010, 1.0990, 1.1000),
    )
    candidate = (
        Candle(times[0], 1.1002, 1.1015, 1.0988, 1.1006),
        Candle(times[1], 1.1007, 1.1012, 1.0987, 1.1001),
    )
    report = compare_h1_candles(baseline, candidate, "GBPUSD", price_tolerance=1e-5)
    assert report.ok
    assert report.as_dict()["directionMatchPct"] == 100.0
    assert report.ohlc_mismatch_count == 2


def test_h1_parity_fails_on_direction_or_timestamp_mismatch():
    t0 = epoch(2026, 8, 21, 0)
    t1 = epoch(2026, 8, 21, 1)
    baseline = (Candle(t0, 1.0, 1.2, 0.9, 1.1), Candle(t1, 1.1, 1.2, 1.0, 1.0))
    candidate = (Candle(t0, 1.0, 1.1, 0.8, 0.9),)
    report = compare_h1_candles(baseline, candidate, "GBPUSD")
    assert not report.ok
    assert len(report.direction_mismatches) == 1
    assert report.missing_candidate == (t1,)
