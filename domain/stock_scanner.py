"""Deterministic, advisory-only D1 stock scanner.

This module deliberately has no dependency on the Forex signal log, MT5,
GBP/XAU symbols, or H-slots.  Every result is calculated from completed local
EOD bars whose date is not later than the requested evaluation date.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date
from enum import Enum
from math import isfinite
from statistics import fmean
from typing import Any, Iterable, Mapping, Sequence


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    WAIT = "WAIT"


@dataclass(frozen=True, slots=True)
class D1Bar:
    symbol: str
    trading_date: date
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True, slots=True)
class D1ScanResult:
    symbol: str
    as_of_date: date
    direction: Direction
    score: float
    rank: int
    reason: str
    data_quality: str
    latest_close: float | None
    latest_volume: float | None

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["as_of_date"] = self.as_of_date.isoformat()
        value["direction"] = self.direction.value
        return value


@dataclass(frozen=True, slots=True)
class StockSelection:
    """Compatibility envelope for callers that expect a selection object."""

    direction: Direction
    action: str
    status: str
    candidates: tuple[D1ScanResult, ...]
    cash_weight: float = 1.0
    requires_user_confirmation: bool = True
    orders_submitted: bool = False


@dataclass(frozen=True, slots=True)
class ScannerPolicy:
    history_window: int = 20
    top_count: int = 3

    def __post_init__(self) -> None:
        if self.history_window < 2 or self.top_count < 1:
            raise ValueError("history_window and top_count must be positive")


def _coerce_bar(symbol: str, value: Any) -> D1Bar | None:
    if isinstance(value, D1Bar):
        return value
    if isinstance(value, Mapping):
        raw_date = value.get("date", value.get("trading_date"))
        try:
            trading_date = raw_date if isinstance(raw_date, date) else date.fromisoformat(str(raw_date))
            return D1Bar(
                symbol=str(value.get("symbol", symbol)).upper(),
                trading_date=trading_date,
                open=float(value.get("open", 0)), high=float(value.get("high", 0)),
                low=float(value.get("low", 0)), close=float(value.get("close", 0)),
                volume=float(value.get("volume", 0) or 0),
            )
        except (TypeError, ValueError):
            return None
    try:
        trading_date = date.fromisoformat(str(getattr(value, "date")))
        return D1Bar(symbol.upper(), trading_date, float(value.open), float(value.high), float(value.low), float(value.close), float(value.volume))
    except (AttributeError, TypeError, ValueError):
        return None


def _normalise_bars(symbol: str, bars: Iterable[Any], as_of_date: date) -> list[D1Bar]:
    unique: dict[date, D1Bar] = {}
    for raw in bars:
        bar = _coerce_bar(symbol, raw)
        if bar is None or bar.trading_date > as_of_date:
            continue
        if not all(isfinite(float(item)) for item in (bar.open, bar.high, bar.low, bar.close, bar.volume)):
            continue
        if bar.close <= 0:
            continue
        unique[bar.trading_date] = bar
    return [unique[key] for key in sorted(unique)]


def scan_symbol_d1(
    symbol: str,
    bars: Iterable[Any],
    as_of_date: date,
    *,
    history_window: int = 20,
) -> D1ScanResult:
    """Evaluate one symbol using only the completed D1 sequence through date."""
    ordered = _normalise_bars(symbol, bars, as_of_date)
    latest = ordered[-1] if ordered else None
    if latest is None:
        return D1ScanResult(symbol.upper(), as_of_date, Direction.WAIT, 0.0, 0, "no completed D1 bar", "MISSING", None, None)
    if len(ordered) < 2:
        return D1ScanResult(symbol.upper(), as_of_date, Direction.WAIT, 0.0, 0, "need two completed D1 bars", "INSUFFICIENT", latest.close, latest.volume)
    window = ordered[-max(2, history_window):]
    previous = window[-2]
    change = latest.close - previous.close
    if change == 0:
        direction = Direction.WAIT
        reason = "latest D1 close unchanged"
    else:
        direction = Direction.BUY if change > 0 else Direction.SELL
        reason = "latest D1 close versus previous completed close"
    returns = [(current.close - prior.close) / prior.close for prior, current in zip(window, window[1:]) if prior.close > 0]
    volatility = fmean(abs(value) for value in returns) if returns else 0.0
    score = abs(change / previous.close) if previous.close > 0 and change else 0.0
    if len(window) > 2 and volatility > 0:
        score /= volatility
    return D1ScanResult(symbol.upper(), as_of_date, direction, round(score, 6), 0, reason, "OK", latest.close, latest.volume)


def scan_d1_linear(
    bars_by_symbol: Mapping[str, Iterable[Any]],
    as_of_date: date,
    *,
    policy: ScannerPolicy | None = None,
    capital: float = 0.0,
) -> dict[str, Any]:
    """Run a stable chronological D1 scan and rank up to three symbols."""
    active = policy or ScannerPolicy()
    if not isfinite(capital) or capital < 0:
        raise ValueError("capital must be finite and non-negative")
    results = [scan_symbol_d1(symbol, bars, as_of_date, history_window=active.history_window) for symbol, bars in sorted(bars_by_symbol.items())]
    eligible = [item for item in results if item.data_quality == "OK" and item.direction is not Direction.WAIT]
    ranked = sorted(eligible, key=lambda item: (-item.score, item.symbol))[:active.top_count]
    rank_by_symbol = {item.symbol: index for index, item in enumerate(ranked, 1)}
    final_results = [D1ScanResult(item.symbol, item.as_of_date, item.direction, item.score, rank_by_symbol.get(item.symbol, 0), item.reason, item.data_quality, item.latest_close, item.latest_volume) for item in results]
    allocation = capital / len(ranked) if ranked else 0.0
    return {
        "schema_version": 2,
        "advisory_only": True,
        "requires_user_confirmation": True,
        "orders_submitted": False,
        "as_of_date": as_of_date.isoformat(),
        "timeframe": "D1",
        "results": [item.to_dict() for item in sorted(final_results, key=lambda item: (item.rank or 999, item.symbol))],
        "recommendations": [{**item.to_dict(), "allocation": allocation} for item in ranked],
        "status": "READY" if ranked else "NO_TRADE",
        "data_source": "LOCAL_EOD_DB",
    }


# Compatibility aliases for the old provider import.  The advisor never uses
# these for decision making; they simply let older plugins read EOD points.
@dataclass(frozen=True, slots=True)
class AfternoonPoint:
    trading_date: date
    price: float
    matched_value: float = 0.0


def extract_h4_signals(*_args: Any, **_kwargs: Any) -> list[Any]:
    """Removed Forex/Stock-DIRECTION bridge; retained as an empty shim."""
    return []


__all__ = ["Direction", "D1Bar", "D1ScanResult", "ScannerPolicy", "StockSelection", "scan_symbol_d1", "scan_d1_linear", "AfternoonPoint"]
