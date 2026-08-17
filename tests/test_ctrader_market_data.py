from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

APP = Path(__file__).resolve().parents[1] / "robot-sltp-pro"
sys.path.insert(0, str(APP))

from ctrader_market_data import (
    canonical_symbol_name,
    choose_authorized_account,
    mt5_broker_day_offset,
    mt5_new_york_close_offset_seconds,
    rebucket_h1_to_mt5_h4,
    resolve_light_symbols,
    snapshot_from_ctrader_rows,
    trendbar_to_candle,
)
from market_data_provider import Candle


def epoch(year: int, month: int, day: int, hour: int) -> int:
    return int(datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp())


def bar(ts_minutes: int, low: int, do: int, dh: int, dc: int):
    return SimpleNamespace(
        utcTimestampInMinutes=ts_minutes,
        low=low,
        deltaOpen=do,
        deltaHigh=dh,
        deltaClose=dc,
    )


def h1(timestamp: int, open_price: float, high: float, low: float, close: float) -> Candle:
    return Candle(timestamp, open_price, high, low, close)


def test_canonical_symbol_name_handles_ctrader_slashes():
    assert canonical_symbol_name("EUR/USD") == "EURUSD"
    assert canonical_symbol_name(" GBP/USD ") == "GBPUSD"


def test_trendbar_conversion_uses_low_plus_deltas_and_minutes_timestamp():
    candle = trendbar_to_candle(bar(100, 110000, 20, 80, 50), 5)
    assert candle.time == 6000
    assert candle.low == 1.1
    assert candle.open == 1.1002
    assert candle.high == 1.1008
    assert candle.close == 1.1005


def test_ic_mt5_new_york_close_offset_is_plus_two_in_winter_plus_three_in_summer():
    assert mt5_new_york_close_offset_seconds(epoch(2026, 1, 15, 12)) == 2 * 3600
    assert mt5_new_york_close_offset_seconds(epoch(2026, 8, 17, 12)) == 3 * 3600
    assert mt5_broker_day_offset(epoch(2026, 1, 15, 12)) == 22 * 3600
    assert mt5_broker_day_offset(epoch(2026, 8, 17, 12)) == 21 * 3600


def test_ic_mt5_offset_tracks_us_dst_transition():
    # US DST begins on the second Sunday of March and ends on the first Sunday of November.
    assert mt5_new_york_close_offset_seconds(epoch(2026, 3, 8, 6)) == 2 * 3600
    assert mt5_new_york_close_offset_seconds(epoch(2026, 3, 8, 8)) == 3 * 3600
    assert mt5_new_york_close_offset_seconds(epoch(2026, 11, 1, 5)) == 3 * 3600
    assert mt5_new_york_close_offset_seconds(epoch(2026, 11, 1, 7)) == 2 * 3600


def test_rebucket_summer_h1_starts_at_21utc_and_aggregates_ohlc():
    start = epoch(2026, 8, 17, 21)
    rows = [
        h1(start, 1.1000, 1.1020, 1.0990, 1.1010),
        h1(start + 3600, 1.1010, 1.1030, 1.1005, 1.1020),
        h1(start + 7200, 1.1020, 1.1040, 1.1010, 1.1030),
        h1(start + 10800, 1.1030, 1.1050, 1.1020, 1.1040),
    ]
    result = rebucket_h1_to_mt5_h4(rows)
    assert result == (Candle(start, 1.1000, 1.1050, 1.0990, 1.1040),)


def test_rebucket_winter_h1_starts_at_22utc():
    start = epoch(2026, 1, 15, 22)
    rows = [h1(start + offset * 3600, 1.1, 1.2, 1.0, 1.15) for offset in range(4)]
    result = rebucket_h1_to_mt5_h4(rows)
    assert len(result) == 1
    assert result[0].time == start


def test_rebucket_skips_incomplete_groups_instead_of_fabricating_bar():
    start = epoch(2026, 8, 17, 21)
    rows = [
        h1(start, 1.1, 1.2, 1.0, 1.15),
        h1(start + 3600, 1.15, 1.2, 1.1, 1.18),
        h1(start + 10800, 1.18, 1.2, 1.1, 1.19),
    ]
    assert rebucket_h1_to_mt5_h4(rows) == ()


def test_account_resolution_is_exact_and_fail_closed():
    accounts = [
        SimpleNamespace(ctidTraderAccountId=1, isLive=False, brokerTitleShort="IC Markets"),
        SimpleNamespace(ctidTraderAccountId=2, isLive=True, brokerTitleShort="IC Markets"),
    ]
    chosen = choose_authorized_account(accounts, account_id=1, environment="demo", broker_hint="ICMarkets")
    assert chosen.ctidTraderAccountId == 1
    with pytest.raises(RuntimeError, match="environment mismatch"):
        choose_authorized_account(accounts, account_id=1, environment="live", broker_hint="ICMarkets")
    with pytest.raises(RuntimeError, match="not authorised"):
        choose_authorized_account(accounts, account_id=9, environment="demo", broker_hint="ICMarkets")


def test_symbol_resolution_requires_exact_canonical_pair():
    rows = [
        SimpleNamespace(symbolName="EUR/USD", symbolId=10),
        SimpleNamespace(symbolName="GBP/USD", symbolId=20),
    ]
    resolved = resolve_light_symbols(rows, ("GBPUSD", "EURUSD"))
    assert resolved["GBPUSD"].symbolId == 20
    assert resolved["EURUSD"].symbolId == 10
    with pytest.raises(RuntimeError, match="symbol not found"):
        resolve_light_symbols(rows, ("USDJPY",))


def test_snapshot_rebuckets_ctrader_h1_and_uses_mt5_day_offset():
    full = SimpleNamespace(symbolId=10, digits=5)
    start = epoch(2026, 8, 17, 21)
    bars = [
        bar((start + index * 3600) // 60, 110000 + index * 10, 0, 100, 50)
        for index in range(4)
    ]
    provider = snapshot_from_ctrader_rows(
        provider_id="ctrader-test",
        symbols={"EURUSD": (10, (full,))},
        h1_bars={"EURUSD": bars},
        as_of_epoch=epoch(2026, 8, 18, 12),
    )
    assert provider.symbols() == ("EURUSD",)
    assert provider.broker_day_offset("EURUSD") == 21 * 3600
    candles = provider.h4_range("EURUSD", start, start + 4 * 3600)
    assert len(candles) == 1
    assert candles[0].time == start
