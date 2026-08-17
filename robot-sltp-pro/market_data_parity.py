from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from market_data_provider import Candle, MarketDataProvider


@dataclass(frozen=True, slots=True)
class CandleParityIssue:
    kind: str
    timestamp: int
    field: str = ""
    baseline: float | int | None = None
    candidate: float | int | None = None


@dataclass(frozen=True, slots=True)
class CandleParityReport:
    baseline_count: int
    candidate_count: int
    matched: int
    issues: tuple[CandleParityIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues

    def as_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "baselineCount": self.baseline_count,
            "candidateCount": self.candidate_count,
            "matched": self.matched,
            "issues": [
                {
                    "kind": issue.kind,
                    "timestamp": issue.timestamp,
                    "field": issue.field,
                    "baseline": issue.baseline,
                    "candidate": issue.candidate,
                }
                for issue in self.issues
            ],
        }


def _price_equal(left: float, right: float, tolerance: float) -> bool:
    return abs(left - right) <= tolerance


def compare_candles(
    baseline: Sequence[Candle] | Iterable[Candle],
    candidate: Sequence[Candle] | Iterable[Candle],
    *,
    price_tolerance: float = 1e-5,
) -> CandleParityReport:
    """Compare broker candles by exact open timestamp and OHLC tolerance.

    Timestamp mismatch is a hard failure because Pattern5 depends on the
    broker-specific H4 boundary. Price differences are tolerated only within
    the configured quote precision.
    """

    baseline_rows = tuple(sorted(baseline, key=lambda item: item.time))
    candidate_rows = tuple(sorted(candidate, key=lambda item: item.time))
    baseline_map = {row.time: row for row in baseline_rows}
    candidate_map = {row.time: row for row in candidate_rows}
    issues: list[CandleParityIssue] = []

    for timestamp in sorted(set(baseline_map) - set(candidate_map)):
        issues.append(CandleParityIssue("missing_candidate", timestamp))
    for timestamp in sorted(set(candidate_map) - set(baseline_map)):
        issues.append(CandleParityIssue("extra_candidate", timestamp))

    matched = 0
    for timestamp in sorted(set(baseline_map) & set(candidate_map)):
        left = baseline_map[timestamp]
        right = candidate_map[timestamp]
        candle_ok = True
        for field in ("open", "high", "low", "close"):
            baseline_value = float(getattr(left, field))
            candidate_value = float(getattr(right, field))
            if not _price_equal(baseline_value, candidate_value, price_tolerance):
                candle_ok = False
                issues.append(
                    CandleParityIssue(
                        "ohlc_mismatch",
                        timestamp,
                        field,
                        baseline_value,
                        candidate_value,
                    )
                )
        if candle_ok:
            matched += 1

    return CandleParityReport(
        baseline_count=len(baseline_rows),
        candidate_count=len(candidate_rows),
        matched=matched,
        issues=tuple(issues),
    )


def compare_provider_range(
    baseline: MarketDataProvider,
    candidate: MarketDataProvider,
    symbol: str,
    start_epoch: int,
    end_epoch: int,
    *,
    price_tolerance: float = 1e-5,
) -> CandleParityReport:
    baseline_offset = baseline.broker_day_offset(symbol)
    candidate_offset = candidate.broker_day_offset(symbol)
    if baseline_offset != candidate_offset:
        return CandleParityReport(
            baseline_count=0,
            candidate_count=0,
            matched=0,
            issues=(
                CandleParityIssue(
                    "day_offset_mismatch",
                    start_epoch,
                    "broker_day_offset",
                    baseline_offset,
                    candidate_offset,
                ),
            ),
        )
    return compare_candles(
        baseline.h4_range(symbol, start_epoch, end_epoch),
        candidate.h4_range(symbol, start_epoch, end_epoch),
        price_tolerance=price_tolerance,
    )


def require_parity(report: CandleParityReport) -> None:
    """Fail closed before a candidate provider may drive production Engine5."""

    if report.ok:
        return
    first = report.issues[0]
    detail = first.kind
    if first.field:
        detail += f" {first.field}"
    raise RuntimeError(
        f"Market-data parity failed: {detail} at {first.timestamp}; "
        f"issues={len(report.issues)}"
    )
