"""Generate confirmation-required VN30 recommendations from H=4 history."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from enum import Enum
import json
import os
from pathlib import Path
import sys
from typing import Mapping, Sequence

from domain.stock_scanner import (
    AdvisoryBacktest,
    H4Signal,
    ScannerPolicy,
    StockScore,
    StockScannerError,
    StockSelection,
    extract_h4_signals,
    score_stock,
    select_top_stocks,
    walk_forward_backtest,
)
from services.ssi_market_data import (
    SSIMarketDataError,
    SSIMarketDataProvider,
    credentials_from_environment,
)
from services.stock_dashboard_publisher import (
    load_dashboard_publisher_config,
    publish_stock_advisory,
)


class AdvisorErrorCode(str, Enum):
    """Stable CLI failure categories."""

    INVALID_HISTORY = "invalid_history"
    STALE_SIGNAL = "stale_signal"
    MT5_BACKFILL_FAILED = "mt5_backfill_failed"
    NO_MARKET_DATA = "no_market_data"


class AdvisorError(RuntimeError):
    """Explicit advisor error with a stable code."""

    def __init__(self, code: AdvisorErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


def build_advisory_payload(
    selection: StockSelection,
    signal: H4Signal,
    backtest: AdvisoryBacktest,
    rejected_count: int,
    data_errors: Sequence[str],
    policy: ScannerPolicy | None = None,
) -> dict[str, object]:
    """Serialize an advisory selection without any execution fields."""
    active_policy = policy or ScannerPolicy()
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "advisory_only": True,
        "requires_user_confirmation": True,
        "orders_submitted": False,
        "status": selection.status,
        "action": selection.action,
        "signal": _signal_payload(signal),
        "candidates": [_candidate_payload(item) for item in selection.candidates],
        "cash_weight": selection.cash_weight,
        "rejected_symbols": rejected_count,
        "data_errors": list(data_errors),
        "backtest": _backtest_payload(backtest),
        "policy": _policy_payload(active_policy),
        "warnings": _advisory_warnings(backtest, active_policy),
    }


def _advisory_warnings(backtest: AdvisoryBacktest, policy: ScannerPolicy) -> list[str]:
    return []


def run_advisor(args: argparse.Namespace) -> dict[str, object]:
    """Run one read-only advisory scan using available HOSE, HNX, UPCoM constituents."""
    if args.backfill_h4:
        _backfill_h4(args.backfill_h4, Path(args.signals_log))
    signals = extract_h4_signals(_load_records(Path(args.signals_log)))
    if not signals:
        raise AdvisorError(AdvisorErrorCode.INVALID_HISTORY, "No valid H=4 signal history")
    current_signal = signals[-1]
    _validate_signal_freshness(current_signal, args.allow_stale)
    policy = ScannerPolicy(hurdle_rate=args.hurdle_bps / 10_000, top_count=args.top_count)
    points, data_errors = _load_vn30_points(current_signal.trading_date, args.history_days)
    scores = _score_current_universe(signals, points, current_signal, policy)
    selection = select_top_stocks(scores, current_signal.direction, args.capital, policy)
    backtest = walk_forward_backtest(signals, points, policy, args.backtest_decisions)
    rejected = sum(not score.eligible for score in scores)
    return build_advisory_payload(selection, current_signal, backtest, rejected, data_errors, policy)


def _load_vn30_points(as_of_date: date, history_days: int) -> tuple[dict, tuple[str, ...]]:
    credentials = credentials_from_environment()
    start_date = as_of_date - timedelta(days=min(365, max(60, history_days)))
    points_by_symbol: dict[str, list] = {}
    errors: list[str] = []
    with SSIMarketDataProvider(credentials) as provider:
        if not provider.has_trading_session(as_of_date):
            raise AdvisorError(AdvisorErrorCode.NO_MARKET_DATA, "No market data session for this date")
        symbols = provider.get_vn30_symbols()
        for index, symbol in enumerate(symbols, start=1):
            print(f"[Local EOD] {index}/{len(symbols)} {symbol}", file=sys.stderr)
            try:
                points_by_symbol[symbol] = provider.get_afternoon_points(symbol, start_date, as_of_date)
            except SSIMarketDataError as error:
                errors.append(f"{symbol}:{error.code.value}")
            except Exception as error:
                errors.append(f"{symbol}:{error}")
    if not points_by_symbol:
        raise AdvisorError(AdvisorErrorCode.NO_MARKET_DATA, "No VN30 afternoon data was available")
    return points_by_symbol, tuple(errors)


def _score_current_universe(
    signals: Sequence[H4Signal],
    points_by_symbol: Mapping[str, Sequence],
    current_signal: H4Signal,
    policy: ScannerPolicy,
) -> list[StockScore]:
    from concurrent.futures import ThreadPoolExecutor

    trading_calendar = sorted({point.trading_date for points in points_by_symbol.values() for point in points})

    def _score_one(item: tuple[str, Sequence]) -> StockScore:
        symbol, points = item
        completed_points = [point for point in points if point.trading_date < current_signal.trading_date]
        close_price = float(getattr(points[-1], "close", 0.0)) if points else 0.0
        ref_price = float(getattr(points[-1], "reference_price", 0.0)) if points else 0.0
        if ref_price <= 0:
            ref_price = float(getattr(points[-1], "open", close_price)) if points else close_price
        pct_change = ((close_price - ref_price) / ref_price * 100.0) if ref_price > 0 else 0.0
        return score_stock(
            symbol,
            signals,
            completed_points,
            current_signal.direction,
            policy,
            trading_calendar,
            close_price=close_price,
            price_change_pct=pct_change,
        )

    with ThreadPoolExecutor(max_workers=16) as executor:
        scores = list(executor.map(_score_one, points_by_symbol.items()))
    return scores


def _load_records(path: Path) -> list[Mapping[str, object]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise AdvisorError(AdvisorErrorCode.INVALID_HISTORY, f"Cannot read {path.name}: {type(error).__name__}") from error
    if not isinstance(data, list):
        raise AdvisorError(AdvisorErrorCode.INVALID_HISTORY, "Signal history must be a JSON list")
    return [item for item in data if isinstance(item, Mapping)]


def _validate_signal_freshness(signal: H4Signal, allow_stale: bool) -> None:
    local_date = datetime.now(timezone(timedelta(hours=7))).date()
    if signal.trading_date == local_date or allow_stale:
        return
    raise AdvisorError(
        AdvisorErrorCode.STALE_SIGNAL,
        f"Latest H=4 signal is {signal.trading_date.isoformat()}, not {local_date.isoformat()}",
    )


def _backfill_h4(session_count: int, signals_log: Path) -> None:
    import mt5_signal_bot

    mt5_signal_bot._SIGNALS_LOG = str(signals_log.resolve())
    was_ready = mt5_signal_bot.mt5_ready
    if not was_ready and not mt5_signal_bot.try_init_mt5():
        raise AdvisorError(AdvisorErrorCode.MT5_BACKFILL_FAILED, "MT5 initialization failed")
    try:
        rebuilt = mt5_signal_bot.rebuild_h4_history(session_count=session_count)
        if rebuilt == 0:
            raise AdvisorError(AdvisorErrorCode.MT5_BACKFILL_FAILED, "No H=4 sessions were rebuilt")
    finally:
        if not was_ready:
            mt5_signal_bot.mt5.shutdown()
            mt5_signal_bot.mt5_ready = False


def _signal_payload(signal: H4Signal) -> dict[str, object]:
    return {
        "date": signal.trading_date.isoformat(),
        "direction": signal.direction.name,
        "holding_window": "13:05 to next trading session 13:05",
    }


def _candidate_payload(candidate: object) -> dict[str, object]:
    score = candidate.score
    return {
        "rank": candidate.rank,
        "symbol": candidate.symbol,
        "weight": candidate.weight,
        "capital": candidate.capital,
        "close_price": getattr(score, "close_price", 0.0),
        "price_change_pct": getattr(score, "price_change_pct", 0.0),
        "hit_rate": score.hit_rate,
        "conditional_hit_rate": score.conditional_hit_rate,
        "conditional_edge": score.conditional_edge,
        "r_squared": score.r_squared,
    }


def _backtest_payload(backtest: AdvisoryBacktest) -> dict[str, object]:
    return {
        "requested_decisions": backtest.requested_decisions,
        "evaluated_decisions": backtest.evaluated_decisions,
        "hit_rate": backtest.hit_rate,
        "mean_aligned_return": backtest.mean_aligned_return,
        "met_requested_decisions": backtest.met_requested_decisions,
    }


def _policy_payload(policy: ScannerPolicy) -> dict[str, object]:
    return {
        "window_size": policy.window_size,
        "minimum_direction_samples": policy.minimum_direction_samples,
        "minimum_hit_rate": policy.minimum_hit_rate,
        "minimum_conditional_hit_rate": policy.minimum_conditional_hit_rate,
        "hurdle_bps": policy.hurdle_rate * 10_000,
        "top_count": policy.top_count,
    }


def _write_payload(payload: Mapping[str, object], output: str | None) -> None:
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if not output:
        if hasattr(sys.stdout, "buffer"):
            try:
                sys.stdout.buffer.write(rendered.encode("utf-8") + b"\n")
                return
            except Exception:
                pass
        print(rendered)
        return
    path = Path(output).resolve()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(rendered, encoding="utf-8")
    temporary.replace(path)
    print(f"Recommendation written to {path}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="HOSE HNX UPCoM H=4 recommendation-only scanner")
    parser.add_argument("--signals-log", default="signals_log.json")
    parser.add_argument("--capital", type=float, default=_environment_float("STOCK_DEPLOYABLE_CAPITAL", 0.0))
    parser.add_argument("--hurdle-bps", type=float, default=_environment_float("STOCK_HURDLE_BPS", 0.0))
    parser.add_argument("--top-count", type=int, default=0, help="Max candidates (0 = all eligible)")
    parser.add_argument("--history-days", type=int, default=365)
    parser.add_argument("--backtest-decisions", type=int, default=250)
    parser.add_argument("--backfill-h4", nargs="?", const=260, type=int, default=0)
    parser.add_argument("--allow-stale", action="store_true", help="Research only: allow a non-current H=4 signal")
    parser.add_argument("--output", help="Optional advisory JSON output path")
    return parser


def _environment_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point; produces recommendations but has no execution capability."""
    args = _build_parser().parse_args(argv)
    try:
        payload = run_advisor(args)
    except (AdvisorError, SSIMarketDataError, StockScannerError, RuntimeError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 2
    _write_payload(payload, args.output)
    _publish_dashboard(payload, Path(args.signals_log))
    return 0


def _publish_dashboard(payload: Mapping[str, object], signals_log: Path) -> None:
    config = load_dashboard_publisher_config(signals_log.resolve().parent)
    result = publish_stock_advisory(payload, config)
    message = "pushed" if result.pushed else result.status
    print(f"[DASHBOARD] Stock advisor: {message}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
