from __future__ import annotations

import json
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import MetaTrader5 as mt5

from market_data_provider import MT5MarketDataProvider, MarketDataProvider
from services.mt5_terminal_service import ensure_mt5_profile_connected

WATCHLIST = ["GBPUSD", "EURUSD"]
CACHE_PATH = Path(__file__).resolve().parent / "pattern5_cache.json"
CACHE_MAX_AGE_SECONDS = 300
T, G = "T", "G"
ANCHOR_HOUR = {3: 4, 7: 8, 9: 12, 12: 16, 14: 20}
BLOCKS = [3, 7, 9, 12, 14]
DAY_NAMES = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6"]
DAY0 = date(1970, 1, 1)
CURRENCY = {"USD", "EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD", "XAU", "XAG"}
KNOWN_AFFIX = {"M", "A", "I", "C", "R", "X", "Z", "H", "B", "S", "T", "E", "F", "K", "V", "PRO", "RAW", "ECN", "STD", "FX", "SPOT", "CASH", "PLUS", "MINI", "LIVE", "TEST"}
CLASSES = {
    1: ((T, T, T), (G, G, G)),
    2: ((G, T, T), (T, G, G)),
    3: ((G, G, T), (T, T, G)),
    4: ((T, G, T), (G, T, G)),
    5: ((T, G, T, G), (G, T, G, T)),
}
GROUP = {1: "Sw", 2: "Sw", 3: "Bt", 4: "Bt", 5: "Sw"}
CACHE_SCHEMA = 11
VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def flip_signal(signal: str) -> str:
    if signal == "BUY":
        return "SELL"
    if signal == "SELL":
        return "BUY"
    raise ValueError(f"Unknown signal: {signal}")


def signal_from_base(directions: list[str], group: str) -> str:
    """Derive signal from candle 4 (oldest lookback candle) and Sw/Bt group."""
    if len(directions) < 4:
        raise ValueError("Need all four lookback candle directions")
    base = directions[3]
    normalized_group = group.casefold()
    if normalized_group == "sw":
        direction = G if base == T else T
    elif normalized_group == "bt":
        direction = base
    else:
        raise ValueError(f"Unknown Pattern5 group: {group}")
    return "BUY" if direction == T else "SELL"


def _first_weekday_day(day: date, weekday: int) -> int:
    first = day.replace(day=1)
    return 1 + ((weekday - first.weekday()) % 7)


def _h3_thursday_reverse(day: date) -> bool:
    cursor = day.replace(day=1)
    while cursor <= day:
        if cursor.weekday() == 3 and (cursor - timedelta(days=1)).day in {30, 1}:
            return False
        cursor += timedelta(days=1)
    return True


def should_reverse_signal(block: int, day: date) -> bool:
    weekday = day.weekday()
    if block == 3:
        if weekday == 0:
            return True
        if weekday == 3:
            return _h3_thursday_reverse(day)
        if weekday == 4:
            return _first_weekday_day(day, 4) in {3, 4, 7}
        return False
    if block == 7:
        return weekday in {1, 4}
    if block == 9:
        return weekday in {3, 4}
    if block == 12:
        return weekday != 2
    if block == 14:
        return weekday <= 4
    return False


def pattern_text(pattern_id: int, directions: list[str]) -> str:
    length = 4 if pattern_id == 5 else 3
    return " ".join(directions[:length])


def classify5(directions: list[str]) -> tuple[int | None, bool]:
    d4 = tuple(directions[:4])
    if d4 == CLASSES[5][0]:
        return 5, False
    if d4 == CLASSES[5][1]:
        return 5, True
    p3 = tuple(directions[:3])
    for pattern in (1, 2, 3, 4):
        if p3 == CLASSES[pattern][0]:
            return pattern, False
        if p3 == CLASSES[pattern][1]:
            return pattern, True
    return None, False


def _core(name: str) -> str:
    return re.sub(r"[^A-Za-z]", "", name).upper()


def resolve_symbol(base: str, names: list[str]) -> str | None:
    base_upper = base.upper()
    if base in names:
        return base
    for name in names:
        if _core(name) == base_upper:
            return name
    best, best_score = None, 10**9
    for name in names:
        core = _core(name)
        score = None
        if core.startswith(base_upper):
            suffix = core[len(base_upper):]
            if suffix and suffix not in CURRENCY and (suffix in KNOWN_AFFIX or len(suffix) <= 3):
                score = len(suffix)
        elif core.endswith(base_upper):
            prefix = core[:-len(base_upper)]
            if prefix and prefix not in CURRENCY and (prefix in KNOWN_AFFIX or len(prefix) <= 3):
                score = len(prefix) + 5
        if score is not None and score < best_score:
            best_score, best = score, name
    return best


def broker_day_offset(symbol: str, provider: MarketDataProvider | None = None) -> int:
    source = provider or MT5MarketDataProvider(mt5)
    return source.broker_day_offset(symbol)


def anchor_epoch(day: date, hour: int, offset: int) -> int:
    return (day - DAY0).days * 86400 + hour * 3600 + offset


def prev_trading_day(day: date) -> date:
    return day - timedelta(days=3) if day.weekday() == 0 else day - timedelta(days=1)


def _h4_range_with_warmup(
    symbol: str,
    start: int,
    end: int,
    provider: MarketDataProvider | None = None,
):
    source = provider or MT5MarketDataProvider(mt5)
    rates = source.h4_range(symbol, start, end)
    if len(rates) >= 4:
        return rates
    source.warm_h4(symbol)
    time.sleep(0.05)
    return source.h4_range(symbol, start, end)


def look4(
    symbol: str,
    anchor: int,
    provider: MarketDataProvider | None = None,
) -> tuple[list[str], list[dict[str, float | int | str]]] | None:
    rates = _h4_range_with_warmup(
        symbol,
        anchor - 10 * 86400,
        anchor + 4 * 3600,
        provider=provider,
    )
    candidates = [rate for rate in rates if int(rate.time) < anchor]
    if len(candidates) < 4:
        return None
    chronological = candidates[-4:]
    evidence = []
    for index, rate in enumerate(chronological, start=1):
        open_price = float(rate.open)
        close_price = float(rate.close)
        evidence.append({
            "index": index,
            "time": int(rate.time),
            "open": open_price,
            "high": float(rate.high),
            "low": float(rate.low),
            "close": close_price,
            "direction": T if close_price > open_price else G,
        })
    directions = [str(candle["direction"]) for candle in reversed(evidence)]
    return directions, evidence


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def vietnam_today() -> date:
    return datetime.now(VIETNAM_TZ).date()


def build_signal_cell(
    symbol: str,
    day: date,
    hour: int,
    offset: int,
    provider: MarketDataProvider | None = None,
) -> tuple[Any, str]:
    lookback_day = prev_trading_day(day)
    lookback = look4(
        symbol,
        anchor_epoch(lookback_day, ANCHOR_HOUR[hour], offset),
        provider=provider,
    )
    if not lookback:
        return "", ""
    directions, evidence = lookback
    pattern_id, _mirrored = classify5(directions)
    if pattern_id is None:
        return "", ""
    group = GROUP[pattern_id]
    base_signal = signal_from_base(directions, group)
    reversed_signal = should_reverse_signal(hour, day)
    signal = flip_signal(base_signal) if reversed_signal else base_signal
    sequence = pattern_text(pattern_id, directions)
    cell = {
        "group": group,
        "baseSignal": base_signal,
        "signal": signal,
        "reversed": reversed_signal,
        "label": f"{group} ({'Tăng' if signal == 'BUY' else 'Giảm'})",
        "pattern": sequence,
        "evidence": evidence,
    }
    reverse_text = "Reverse" if reversed_signal else "Normal"
    detail = f"{group} · Base {base_signal} · {reverse_text} → {signal} · {sequence}"
    return cell, detail


def build_table(
    symbol: str,
    week_start: date | None = None,
    as_of: date | None = None,
    provider: MarketDataProvider | None = None,
) -> tuple[list[date], dict[int, list[Any]], dict[int, list[str]]]:
    current_day = as_of or vietnam_today()
    week = week_start or monday_of(current_day)
    days = [week + timedelta(days=index) for index in range(5)]
    offset = broker_day_offset(symbol, provider=provider)
    rows: dict[int, list[Any]] = {hour: [""] * 5 for hour in BLOCKS}
    detail = {hour: [""] * 5 for hour in BLOCKS}
    for day_index, day in enumerate(days):
        if day > current_day:
            continue
        for hour in BLOCKS:
            cell, cell_detail = build_signal_cell(symbol, day, hour, offset, provider=provider)
            rows[hour][day_index] = cell
            detail[hour][day_index] = cell_detail
    return days, rows, detail


def build_h14_reference(
    symbol: str,
    days: list[date],
    rows: dict[int, list[Any]],
    provider: MarketDataProvider | None = None,
) -> dict[str, str] | None:
    signals = rows.get(14, [])
    latest_index = next((index for index in range(min(len(days), len(signals)) - 1, -1, -1) if signals[index]), -1)
    if latest_index < 0:
        return None
    reference_day = prev_trading_day(days[latest_index])
    reference_cell: Any = ""
    try:
        reference_index = days.index(reference_day)
    except ValueError:
        reference_index = -1
    if reference_index >= 0:
        reference_cell = signals[reference_index]
    else:
        offset = broker_day_offset(symbol, provider=provider)
        reference_cell, _detail = build_signal_cell(symbol, reference_day, 14, offset, provider=provider)
    if not reference_cell:
        return None
    return {
        "date": reference_day.isoformat(),
        "display": reference_day.strftime("%d/%m"),
        "group": str(reference_cell["group"]),
        "pattern": str(reference_cell["pattern"]),
    }


def _cache_key(profile: str, week_start: str) -> str:
    return f"v{CACHE_SCHEMA}|{profile}|{week_start}"


def _load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict[str, Any]) -> None:
    temp = CACHE_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(cache, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(temp, CACHE_PATH)


def render_profile_cached(profile: str, selected: list[str] | None = None, week_start: str | None = None, force: bool = False) -> dict[str, Any]:
    resolved_week = week_start or monday_of(vietnam_today()).isoformat()
    key = _cache_key(profile, resolved_week)
    cache = _load_cache()
    cached = cache.get(key)
    if not force and isinstance(cached, dict) and (time.time() - float(cached.get("generatedAtEpoch", 0))) < CACHE_MAX_AGE_SECONDS:
        result = cached.get("data")
        if isinstance(result, dict):
            return {**result, "cacheHit": True}
    result = render_profile(profile, selected=selected, week_start=resolved_week)
    cache[key] = {"generatedAtEpoch": time.time(), "data": result}
    _save_cache(cache)
    return {**result, "cacheHit": False}


def render_profile_with_provider(
    profile: str,
    provider: MarketDataProvider,
    selected: list[str] | None = None,
    week_start: str | None = None,
) -> dict[str, Any]:
    """Render Engine5 using any provider that preserves broker candle boundaries."""

    names = list(provider.symbols())
    monday = date.fromisoformat(week_start) if week_start else None
    instruments = selected or WATCHLIST
    tables = []
    for base in instruments:
        symbol = resolve_symbol(base, names)
        if symbol is None:
            tables.append({"base": base, "symbol": None, "error": "KHONG TIM THAY SYMBOL BROKER"})
            continue
        days, rows, detail = build_table(symbol, monday, provider=provider)
        h14_reference = build_h14_reference(symbol, days, rows, provider=provider)
        tables.append({
            "base": base,
            "symbol": symbol,
            "h14Reference": h14_reference,
            "days": [
                {
                    "name": DAY_NAMES[index],
                    "date": days[index].isoformat(),
                    "display": days[index].strftime("%d/%m"),
                }
                for index in range(5)
            ],
            "rows": {str(hour): rows[hour] for hour in BLOCKS},
            "detail": {str(hour): detail[hour] for hour in BLOCKS},
        })
    return {
        "profile": profile,
        "dataProvider": provider.provider_id,
        "weekStart": (monday or monday_of(vietnam_today())).isoformat(),
        "blocks": BLOCKS,
        "tables": tables,
    }


def render_profile(profile: str, selected: list[str] | None = None, week_start: str | None = None) -> dict[str, Any]:
    raw = __import__("json").loads(open(__import__("pathlib").Path(__file__).resolve().parent.parent / "profiles.json", encoding="utf-8").read())
    cfg = raw.get(profile)
    if not isinstance(cfg, dict):
        raise RuntimeError(f"Unknown profile: {profile}")

    # Pattern5 is a passive/read-only consumer. Selecting a profile, periodic
    # publishing, or refreshing Pattern5 must never launch a terminal that the
    # user intentionally closed. MetaTrader5.initialize(path=...) can itself
    # start terminal64.exe, so always go through the attach-only guard first.
    connection = ensure_mt5_profile_connected(
        {**cfg, "profile_name": profile},
        mt5_module=mt5,
        timeout_seconds=5,
        allow_process_start=False,
    )
    if not connection.ok:
        code = connection.failure_code or "MT5_ATTACH_FAILED"
        raise RuntimeError(f"MT5 attach only [{code}]: {connection.message}")
    try:
        return render_profile_with_provider(
            profile,
            MT5MarketDataProvider(mt5),
            selected=selected,
            week_start=week_start,
        )
    finally:
        mt5.shutdown()
