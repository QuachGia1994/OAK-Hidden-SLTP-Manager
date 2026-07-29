"""Pure domain logic for H=4 Vietnamese stock recommendations."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from math import fsum, isfinite, log
from statistics import fmean
from typing import Iterable, Mapping, Sequence


MINIMUM_SIGNAL_LOGIC_VERSION = 58


class Direction(Enum):
    """Canonical H=4 direction encoded for return alignment."""

    BUY = 1
    SELL = -1

    @classmethod
    def parse(cls, value: object) -> Direction | None:
        """Return a direction for a supported string, otherwise ``None``."""
        if value == "BUY":
            return cls.BUY
        if value == "SELL":
            return cls.SELL
        return None


class StockScannerErrorCode(str, Enum):
    """Stable error categories for scanner callers."""

    INVALID_POLICY = "invalid_policy"
    INVALID_CAPITAL = "invalid_capital"


class StockScannerError(ValueError):
    """Explicit scanner error with a stable machine-readable code."""

    def __init__(self, code: StockScannerErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class H4Signal:
    """One final current-contract H=4 XAUUSD direction for a broker date."""

    trading_date: date
    direction: Direction


@dataclass(frozen=True, slots=True)
class AfternoonPoint:
    """Executable afternoon reference price for one stock session."""

    trading_date: date
    price: float
    matched_value: float = 0.0


@dataclass(frozen=True, slots=True)
class ForwardSample:
    """One completed afternoon-to-next-afternoon outcome."""

    signal_date: date
    exit_date: date
    direction: Direction
    forward_return: float
    aligned_return: float


@dataclass(frozen=True, slots=True)
class ScannerPolicy:
    """Thresholds for the default recommendation-only scanner.

    Thresholds are calibrated for the Vietnamese stock market where H4 signal
    alignment with next-day stock movement typically ranges 40-65% in any
    rolling 25-session window.

    minimum_hit_rate: overall aligned hit rate (both BUY+SELL sessions)
    minimum_conditional_hit_rate: hit rate on sessions matching current direction
    """

    window_size: int = 25
    minimum_direction_samples: int = 8
    minimum_hit_rate: float = 0.55          # realistic for VN market (max seen ~64%)
    minimum_conditional_hit_rate: float = 0.60  # stocks must outperform on direction days
    hurdle_rate: float = 0.0
    maximum_absolute_return: float = 0.15
    top_count: int = 3  # 0 means return ALL eligible candidates

    def __post_init__(self) -> None:
        if self.window_size < 2 or self.top_count < 0:
            raise StockScannerError(StockScannerErrorCode.INVALID_POLICY, "Window and top count must be positive")
        if not 1 <= self.minimum_direction_samples <= self.window_size:
            raise StockScannerError(StockScannerErrorCode.INVALID_POLICY, "Direction samples must fit the window")
        rates = (self.minimum_hit_rate, self.minimum_conditional_hit_rate, self.hurdle_rate)
        if not all(isfinite(value) for value in rates) or not isfinite(self.maximum_absolute_return):
            raise StockScannerError(StockScannerErrorCode.INVALID_POLICY, "Policy rates must be finite")
        if not 0 <= self.minimum_hit_rate <= 1:
            raise StockScannerError(StockScannerErrorCode.INVALID_POLICY, "Hit rate must be between zero and one")
        if not 0 <= self.minimum_conditional_hit_rate <= 1:
            raise StockScannerError(StockScannerErrorCode.INVALID_POLICY, "Conditional hit rate must be between zero and one")
        if self.hurdle_rate < 0:
            raise StockScannerError(StockScannerErrorCode.INVALID_POLICY, "Hurdle rate cannot be negative")
        if self.maximum_absolute_return <= 0:
            raise StockScannerError(StockScannerErrorCode.INVALID_POLICY, "Maximum return must be positive")


@dataclass(frozen=True, slots=True)
class StockScore:
    """Evidence used to rank one stock for the current H=4 direction."""

    symbol: str
    sample_count: int
    direction_sample_count: int
    hit_rate: float
    conditional_hit_rate: float
    mean_aligned_return: float
    conditional_edge: float
    beta: float
    r_squared: float
    eligible: bool
    close_price: float = 0.0
    price_change_pct: float = 0.0
    rejection_reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StockCandidate:
    """One advisory candidate occupying one of three equal slots."""

    symbol: str
    rank: int
    weight: float
    capital: float
    score: StockScore


@dataclass(frozen=True, slots=True)
class StockSelection:
    """Advisory result that can never represent a submitted order."""

    direction: Direction
    action: str
    status: str
    candidates: tuple[StockCandidate, ...]
    cash_weight: float
    requires_user_confirmation: bool = field(default=True, init=False)
    orders_submitted: bool = field(default=False, init=False)


@dataclass(frozen=True, slots=True)
class AdvisoryBacktest:
    """Walk-forward evidence for recommendations, never simulated orders."""

    requested_decisions: int
    evaluated_decisions: int
    hit_rate: float
    mean_aligned_return: float
    met_requested_decisions: bool
    orders_submitted: bool = field(default=False, init=False)


def extract_h4_signals(records: Iterable[Mapping[str, object]], limit: int | None = None) -> list[H4Signal]:
    """Extract current-contract XAUUSD H=4 signals from the JSON log."""
    signals_by_date: dict[date, H4Signal] = {}
    for record in records:
        if not _is_current_h4_record(record):
            continue
        trading_date = _record_date(record.get("date"))
        direction = _record_direction(record)
        if trading_date is None or direction is None:
            continue
        signals_by_date[trading_date] = H4Signal(trading_date, direction)
    signals = [signals_by_date[key] for key in sorted(signals_by_date)]
    return signals[-limit:] if limit is not None else signals


def build_forward_samples(
    signals: Sequence[H4Signal],
    points: Sequence[AfternoonPoint],
    trading_calendar: Sequence[date] | None = None,
) -> list[ForwardSample]:
    """Join signals to the next available afternoon price without look-ahead."""
    ordered_points = _valid_unique_points(points)
    point_index = {point.trading_date: index for index, point in enumerate(ordered_points)}
    next_session = _next_session_map(trading_calendar)
    samples: list[ForwardSample] = []
    for signal in sorted(signals, key=lambda item: item.trading_date):
        index = point_index.get(signal.trading_date)
        if index is None or index + 1 >= len(ordered_points):
            continue
        entry, exit_point = ordered_points[index], ordered_points[index + 1]
        if next_session is not None and next_session.get(entry.trading_date) != exit_point.trading_date:
            continue
        forward_return = log(exit_point.price / entry.price)
        samples.append(_forward_sample(signal, exit_point.trading_date, forward_return))
    return samples


def score_stock(
    symbol: str,
    signals: Sequence[H4Signal],
    points: Sequence[AfternoonPoint],
    current_direction: Direction,
    policy: ScannerPolicy | None = None,
    trading_calendar: Sequence[date] | None = None,
    close_price: float = 0.0,
    price_change_pct: float = 0.0,
) -> StockScore:
    """Score one stock using only completed outcomes in the trailing window."""
    active_policy = policy or ScannerPolicy()
    samples = build_forward_samples(signals, points, trading_calendar)
    return _score_completed_samples(symbol, samples, current_direction, active_policy, close_price, price_change_pct)


def walk_forward_backtest(
    signals: Sequence[H4Signal],
    points_by_symbol: Mapping[str, Sequence[AfternoonPoint]],
    policy: ScannerPolicy | None = None,
    decision_limit: int = 250,
) -> AdvisoryBacktest:
    """Evaluate rankings using only outcomes completed before each decision."""
    if decision_limit < 1:
        raise StockScannerError(StockScannerErrorCode.INVALID_POLICY, "Decision limit must be positive")
    active_policy = policy or ScannerPolicy()
    trading_calendar = sorted({point.trading_date for points in points_by_symbol.values() for point in points})
    samples_by_symbol = {
        symbol: build_forward_samples(signals, points, trading_calendar)
        for symbol, points in points_by_symbol.items()
    }
    outcomes = []
    for signal in sorted(signals, key=lambda item: item.trading_date):
        outcome = _backtest_decision(signal, samples_by_symbol, active_policy)
        if outcome is not None:
            outcomes.append(outcome)
    evaluated = outcomes[-decision_limit:]
    hit_rate = _return_hit_rate(evaluated, active_policy.hurdle_rate)
    mean_return = fmean(evaluated) if evaluated else 0.0
    return AdvisoryBacktest(decision_limit, len(evaluated), hit_rate, mean_return, len(evaluated) >= decision_limit)


def _score_completed_samples(
    symbol: str,
    samples: Sequence[ForwardSample],
    current_direction: Direction,
    policy: ScannerPolicy,
    close_price: float = 0.0,
    price_change_pct: float = 0.0,
) -> StockScore:
    usable = [sample for sample in samples if abs(sample.forward_return) <= policy.maximum_absolute_return]
    active_samples = usable[-policy.window_size :]
    conditional = [sample for sample in active_samples if sample.direction is current_direction]
    metrics = _score_metrics(active_samples, conditional, policy.hurdle_rate)
    beta, r_squared = _linear_fit(active_samples)
    reasons = _rejection_reasons(active_samples, conditional, metrics, beta, policy)
    return StockScore(
        symbol=symbol.upper(),
        sample_count=len(active_samples),
        direction_sample_count=len(conditional),
        hit_rate=metrics["hit_rate"],
        conditional_hit_rate=metrics["conditional_hit_rate"],
        mean_aligned_return=metrics["mean_aligned_return"],
        conditional_edge=metrics["conditional_edge"],
        beta=beta,
        r_squared=r_squared,
        eligible=not reasons,
        close_price=close_price,
        price_change_pct=price_change_pct,
        rejection_reasons=tuple(reasons),
    )


def _backtest_decision(
    signal: H4Signal,
    samples_by_symbol: Mapping[str, Sequence[ForwardSample]],
    policy: ScannerPolicy,
) -> float | None:
    scores: list[StockScore] = []
    outcomes: dict[str, ForwardSample] = {}
    for symbol, samples in samples_by_symbol.items():
        outcome = next((item for item in samples if item.signal_date == signal.trading_date), None)
        if outcome is None:
            continue
        completed = [item for item in samples if item.exit_date < signal.trading_date]
        scores.append(_score_completed_samples(symbol, completed, signal.direction, policy))
        outcomes[symbol] = outcome
    selection = select_top_stocks(scores, signal.direction, capital=0.0, policy=policy)
    aligned = [outcomes[item.symbol].aligned_return for item in selection.candidates]
    return fmean(aligned) if aligned else None


def _return_hit_rate(values: Sequence[float], hurdle_rate: float) -> float:
    if not values:
        return 0.0
    return sum(value > hurdle_rate for value in values) / len(values)


def select_top_stocks(
    scores: Sequence[StockScore],
    direction: Direction,
    capital: float,
    policy: ScannerPolicy | None = None,
) -> StockSelection:
    """Return equal advisory slots for eligible candidates; never submit an order."""
    if not isfinite(capital) or capital < 0:
        raise StockScannerError(StockScannerErrorCode.INVALID_CAPITAL, "Capital must be finite and non-negative")
    active_policy = policy or ScannerPolicy()
    ranked = sorted((score for score in scores if score.eligible), key=_ranking_key, reverse=True)
    if active_policy.top_count and active_policy.top_count > 0:
        selected = ranked[: active_policy.top_count]
        target_slots = active_policy.top_count
    else:
        selected = ranked
        target_slots = len(selected) if selected else 1

    candidates = _build_candidates(selected, capital, target_slots)
    status = "NO_TRADE" if not candidates else "READY" if len(candidates) == target_slots else "PARTIAL"
    action = "BUY_OR_HOLD" if direction is Direction.BUY else "SELL_OR_AVOID"
    cash_weight = max(0.0, 1.0 - len(candidates) / target_slots) if target_slots > 0 else 1.0
    return StockSelection(direction, action, status, candidates, cash_weight)


def _record_hour(record: Mapping[str, object]) -> int | None:
    try:
        return int(record.get("hour", -1))
    except (TypeError, ValueError):
        return None


def _is_current_h4_record(record: Mapping[str, object]) -> bool:
    try:
        logic_version = int(record.get("logic_version"))
    except (TypeError, ValueError):
        return False
    return _record_hour(record) == 4 and logic_version >= MINIMUM_SIGNAL_LOGIC_VERSION


def _record_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def _record_direction(record: Mapping[str, object]) -> Direction | None:
    pair_dirs = record.get("pair_dirs")
    if not isinstance(pair_dirs, Mapping):
        return None
    return Direction.parse(pair_dirs.get("XAUUSD"))


def _valid_unique_points(points: Sequence[AfternoonPoint]) -> list[AfternoonPoint]:
    unique = {point.trading_date: point for point in points if isfinite(point.price) and point.price > 0}
    return [unique[key] for key in sorted(unique)]


def _next_session_map(trading_calendar: Sequence[date] | None) -> dict[date, date] | None:
    if trading_calendar is None:
        return None
    ordered = sorted(set(trading_calendar))
    return {current: following for current, following in zip(ordered, ordered[1:])}


def _forward_sample(signal: H4Signal, exit_date: date, forward_return: float) -> ForwardSample:
    aligned_return = signal.direction.value * forward_return
    return ForwardSample(signal.trading_date, exit_date, signal.direction, forward_return, aligned_return)


def _score_metrics(
    samples: Sequence[ForwardSample],
    conditional: Sequence[ForwardSample],
    hurdle_rate: float,
) -> dict[str, float]:
    hit_rate = _hit_rate(samples, hurdle_rate)
    conditional_hit_rate = _hit_rate(conditional, hurdle_rate)
    mean_aligned = fmean(item.aligned_return for item in samples) if samples else 0.0
    conditional_edge = fmean(item.aligned_return for item in conditional) if conditional else 0.0
    return {
        "hit_rate": hit_rate,
        "conditional_hit_rate": conditional_hit_rate,
        "mean_aligned_return": mean_aligned,
        "conditional_edge": conditional_edge,
    }


def _hit_rate(samples: Sequence[ForwardSample], hurdle_rate: float) -> float:
    if not samples:
        return 0.0
    hits = sum(item.aligned_return > hurdle_rate for item in samples)
    return hits / len(samples)


def _linear_fit(samples: Sequence[ForwardSample]) -> tuple[float, float]:
    if len(samples) < 2:
        return 0.0, 0.0
    xs = [float(item.direction.value) for item in samples]
    ys = [item.forward_return for item in samples]
    x_mean, y_mean = fmean(xs), fmean(ys)
    ss_x = fsum((value - x_mean) ** 2 for value in xs)
    if ss_x == 0:
        return 0.0, 0.0
    beta = fsum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / ss_x
    predictions = [y_mean + beta * (x - x_mean) for x in xs]
    total = fsum((value - y_mean) ** 2 for value in ys)
    residual = fsum((value - prediction) ** 2 for value, prediction in zip(ys, predictions))
    return beta, 0.0 if total == 0 else max(0.0, 1.0 - residual / total)


def _rejection_reasons(
    samples: Sequence[ForwardSample],
    conditional: Sequence[ForwardSample],
    metrics: Mapping[str, float],
    beta: float,
    policy: ScannerPolicy,
) -> list[str]:
    reasons: list[str] = []
    if len(samples) < policy.window_size:
        reasons.append("insufficient_history")
    if len(conditional) < policy.minimum_direction_samples:
        reasons.append("insufficient_direction_samples")
    if metrics["hit_rate"] < policy.minimum_hit_rate:
        reasons.append("hit_rate")
    if metrics["conditional_hit_rate"] < policy.minimum_conditional_hit_rate:
        reasons.append("conditional_hit_rate")
    if metrics["conditional_edge"] <= policy.hurdle_rate:
        reasons.append("conditional_edge")
    if beta <= 0:
        reasons.append("non_positive_beta")
    return reasons


def _ranking_key(score: StockScore) -> tuple[float, float, float, float, str]:
    return (
        score.conditional_edge,
        score.conditional_hit_rate,
        score.hit_rate,
        score.r_squared,
        score.symbol,
    )


def _build_candidates(scores: Sequence[StockScore], capital: float, top_count: int) -> tuple[StockCandidate, ...]:
    slot_weight = 1.0 / top_count
    return tuple(
        StockCandidate(score.symbol, rank, slot_weight, capital * slot_weight, score)
        for rank, score in enumerate(scores, start=1)
    )
