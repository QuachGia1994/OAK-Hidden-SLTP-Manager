from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo

from market_data_provider import Candle


H1_SNAPSHOT_SCHEMA = 1
NEW_YORK_TZ = ZoneInfo("America/New_York")


def candle_direction(candle: Candle) -> str:
    return "T" if float(candle.close) > float(candle.open) else "G"


def icmarkets_server_offset_seconds(epoch: int) -> int:
    """IC Markets MT5 server wall offset: UTC+2 winter, UTC+3 New-York DST."""
    instant = datetime.fromtimestamp(int(epoch), tz=timezone.utc).astimezone(NEW_YORK_TZ)
    daylight = instant.dst() or timedelta(0)
    return 3 * 3600 if daylight != timedelta(0) else 2 * 3600


def icmarkets_server_wall_epoch(utc_epoch: int) -> int:
    """Encode a UTC H1 opening instant the same way MT5 Python exposes server-wall bars."""
    return int(utc_epoch) + icmarkets_server_offset_seconds(int(utc_epoch))


def latest_broker_date(candles_by_symbol: dict[str, Sequence[Candle]]) -> str:
    latest = max(
        (int(candle.time) for candles in candles_by_symbol.values() for candle in candles),
        default=0,
    )
    if latest <= 0:
        raise RuntimeError("H1 snapshot has no candles")
    return datetime.fromtimestamp(latest, tz=timezone.utc).date().isoformat()


def filter_broker_date(candles: Iterable[Candle], broker_date: str) -> tuple[Candle, ...]:
    return tuple(
        candle
        for candle in sorted(candles, key=lambda row: row.time)
        if datetime.fromtimestamp(int(candle.time), tz=timezone.utc).date().isoformat() == broker_date
    )


def scanner_relevant_h1(candles: Iterable[Candle]) -> tuple[Candle, ...]:
    """Keep only broker-wall H01..H16, the H1 hours that can feed scanner rules."""
    return tuple(
        candle
        for candle in sorted(candles, key=lambda row: row.time)
        if 1 <= datetime.fromtimestamp(int(candle.time), tz=timezone.utc).hour <= 16
    )


def build_h1_snapshot_payload(
    *,
    provider: str,
    candles_by_symbol: dict[str, Sequence[Candle]],
    broker_date: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected_date = str(broker_date or latest_broker_date(candles_by_symbol))
    output: dict[str, list[dict[str, Any]]] = {}
    for symbol, candles in candles_by_symbol.items():
        rows = filter_broker_date(candles, selected_date)
        if not rows:
            continue
        output[str(symbol)] = [
            {
                **candle.as_dict(),
                "direction": candle_direction(candle),
            }
            for candle in rows
        ]
    if not output:
        raise RuntimeError(f"No H1 candles available for broker date {selected_date}")
    return {
        "schemaVersion": H1_SNAPSHOT_SCHEMA,
        "timeframe": "H1",
        "provider": str(provider),
        "brokerDate": selected_date,
        "candles": output,
        "metadata": dict(metadata or {}),
    }


def parse_h1_snapshot(payload: dict[str, Any]) -> dict[str, tuple[Candle, ...]]:
    if payload.get("schemaVersion") != H1_SNAPSHOT_SCHEMA or payload.get("timeframe") != "H1":
        raise ValueError("Invalid H1 snapshot schema/timeframe")
    raw = payload.get("candles")
    if not isinstance(raw, dict):
        raise ValueError("Invalid H1 snapshot candles")
    parsed: dict[str, tuple[Candle, ...]] = {}
    for symbol, rows in raw.items():
        if not isinstance(rows, list):
            raise ValueError(f"Invalid H1 candle list for {symbol}")
        candles: list[Candle] = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError(f"Invalid H1 candle row for {symbol}")
            candles.append(Candle(
                time=int(row["time"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
            ))
        parsed[str(symbol)] = tuple(sorted(candles, key=lambda candle: candle.time))
    return parsed


@dataclass(frozen=True, slots=True)
class H1ParityReport:
    symbol: str
    baseline_count: int
    candidate_count: int
    common_count: int
    missing_candidate: tuple[int, ...]
    extra_candidate: tuple[int, ...]
    direction_mismatches: tuple[dict[str, Any], ...]
    ohlc_mismatch_count: int
    max_abs_ohlc_diff: float

    @property
    def ok(self) -> bool:
        return (
            not self.missing_candidate
            and not self.extra_candidate
            and not self.direction_mismatches
            and self.baseline_count == self.candidate_count == self.common_count
        )

    def as_dict(self) -> dict[str, Any]:
        direction_matched = self.common_count - len(self.direction_mismatches)
        return {
            "ok": self.ok,
            "symbol": self.symbol,
            "baselineCount": self.baseline_count,
            "candidateCount": self.candidate_count,
            "commonCount": self.common_count,
            "missingCandidate": list(self.missing_candidate),
            "extraCandidate": list(self.extra_candidate),
            "directionMatched": direction_matched,
            "directionMatchPct": round((direction_matched / self.common_count * 100.0) if self.common_count else 0.0, 6),
            "directionMismatches": list(self.direction_mismatches),
            "ohlcMismatchCount": self.ohlc_mismatch_count,
            "maxAbsOhlcDiff": self.max_abs_ohlc_diff,
            "parityRule": "timestamp+T/G direction; OHLC diagnostic only",
        }


def compare_h1_candles(
    baseline: Sequence[Candle],
    candidate: Sequence[Candle],
    symbol: str,
    *,
    price_tolerance: float = 1e-5,
) -> H1ParityReport:
    left = {int(row.time): row for row in baseline}
    right = {int(row.time): row for row in candidate}
    left_times = set(left)
    right_times = set(right)
    common = sorted(left_times & right_times)
    direction_mismatches: list[dict[str, Any]] = []
    ohlc_mismatch_count = 0
    max_diff = 0.0
    for timestamp in common:
        lrow = left[timestamp]
        rrow = right[timestamp]
        ldir = candle_direction(lrow)
        rdir = candle_direction(rrow)
        if ldir != rdir:
            direction_mismatches.append({
                "time": timestamp,
                "baseline": ldir,
                "candidate": rdir,
                "baselineOpen": lrow.open,
                "baselineClose": lrow.close,
                "candidateOpen": rrow.open,
                "candidateClose": rrow.close,
            })
        diffs = [
            abs(lrow.open - rrow.open),
            abs(lrow.high - rrow.high),
            abs(lrow.low - rrow.low),
            abs(lrow.close - rrow.close),
        ]
        row_max = max(diffs)
        max_diff = max(max_diff, row_max)
        if any(diff > price_tolerance for diff in diffs):
            ohlc_mismatch_count += 1
    return H1ParityReport(
        symbol=symbol,
        baseline_count=len(left),
        candidate_count=len(right),
        common_count=len(common),
        missing_candidate=tuple(sorted(left_times - right_times)),
        extra_candidate=tuple(sorted(right_times - left_times)),
        direction_mismatches=tuple(direction_mismatches),
        ohlc_mismatch_count=ohlc_mismatch_count,
        max_abs_ohlc_diff=max_diff,
    )
