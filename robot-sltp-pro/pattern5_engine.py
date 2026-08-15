from __future__ import annotations

import json
import os
import re
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import MetaTrader5 as mt5

WATCHLIST = ["GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD"]
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
CACHE_SCHEMA = 3


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


def broker_day_offset(symbol: str) -> int:
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 2)
    if rates is None or len(rates) < 1:
        raise RuntimeError(f"Khong lay duoc D1 cua {symbol}")
    return int(rates[0]["time"]) % 86400


def anchor_epoch(day: date, hour: int, offset: int) -> int:
    return (day - DAY0).days * 86400 + hour * 3600 + offset


def prev_trading_day(day: date) -> date:
    return day - timedelta(days=3) if day.weekday() == 0 else day - timedelta(days=1)


def look4(symbol: str, anchor: int) -> list[str] | None:
    rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_H4, anchor - 10 * 86400, anchor + 4 * 3600)
    if rates is None:
        return None
    candidates = [rate for rate in rates if int(rate["time"]) < anchor]
    if len(candidates) < 4:
        return None
    return [T if float(rate["close"]) > float(rate["open"]) else G for rate in reversed(candidates[-4:])]


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def build_table(symbol: str, week_start: date | None = None) -> tuple[list[date], dict[int, list[str]], dict[int, list[str]]]:
    week = week_start or monday_of(date.today())
    days = [week + timedelta(days=index) for index in range(5)]
    offset = broker_day_offset(symbol)
    rows = {hour: [""] * 5 for hour in BLOCKS}
    detail = {hour: [""] * 5 for hour in BLOCKS}
    for day_index, day in enumerate(days):
        lookback_day = prev_trading_day(day)
        for hour in BLOCKS:
            directions = look4(symbol, anchor_epoch(lookback_day, ANCHOR_HOUR[hour], offset))
            if not directions:
                continue
            pattern_id, _mirrored = classify5(directions)
            if pattern_id is None:
                continue
            group = GROUP[pattern_id]
            signal = signal_from_base(directions, group)
            sequence = pattern_text(pattern_id, directions)
            rows[hour][day_index] = {
                "group": group,
                "signal": signal,
                "label": f"{group} ({'Tăng' if signal == 'BUY' else 'Giảm'})",
                "pattern": sequence,
            }
            detail[hour][day_index] = f"{group} · {signal} · {sequence}"
    return days, rows, detail


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
    resolved_week = week_start or monday_of(date.today()).isoformat()
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


def render_profile(profile: str, selected: list[str] | None = None, week_start: str | None = None) -> dict[str, Any]:
    raw = __import__("json").loads(open(__import__("pathlib").Path(__file__).resolve().parent.parent / "profiles.json", encoding="utf-8").read())
    cfg = raw.get(profile)
    if not isinstance(cfg, dict):
        raise RuntimeError(f"Unknown profile: {profile}")
    initialized_here = mt5.terminal_info() is None
    if initialized_here and not mt5.initialize(path=cfg.get("path") or None, portable=bool(cfg.get("mt5_portable", False))):
        raise RuntimeError(f"MT5 init fail: {mt5.last_error()}")
    try:
        names = [symbol.name for symbol in (mt5.symbols_get() or [])]
        monday = date.fromisoformat(week_start) if week_start else None
        instruments = selected or WATCHLIST
        tables = []
        for base in instruments:
            symbol = resolve_symbol(base, names)
            if symbol is None:
                tables.append({"base": base, "symbol": None, "error": "KHONG TIM THAY SYMBOL BROKER"})
                continue
            days, rows, detail = build_table(symbol, monday)
            tables.append({
                "base": base,
                "symbol": symbol,
                "days": [{"name": DAY_NAMES[index], "date": days[index].isoformat(), "display": days[index].strftime("%d/%m")} for index in range(5)],
                "rows": {str(hour): rows[hour] for hour in BLOCKS},
                "detail": {str(hour): detail[hour] for hour in BLOCKS},
            })
        return {
            "profile": profile,
            "weekStart": (monday or monday_of(date.today())).isoformat(),
            "blocks": BLOCKS,
            "tables": tables,
        }
    finally:
        if initialized_here:
            mt5.shutdown()
