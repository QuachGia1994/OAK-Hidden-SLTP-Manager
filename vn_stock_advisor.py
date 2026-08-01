"""Run the independent Local EOD D1 stock advisory scanner."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
from typing import Sequence

from domain.stock_scanner import ScannerPolicy, scan_d1_linear
from eod_collector.database import Database
from eod_collector.repository import EODRepository
from services.stock_dashboard_publisher import load_dashboard_publisher_config, publish_stock_advisory


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local EOD D1 advisory scanner")
    parser.add_argument("--db-path", default="data/market.db")
    parser.add_argument("--as-of-date", default="")
    parser.add_argument("--capital", type=float, default=0.0)
    parser.add_argument("--history-window", type=int, default=20)
    parser.add_argument("--output", default="stock_recommendation.json")
    return parser


def run_advisor(args: argparse.Namespace) -> dict[str, object]:
    as_of = date.fromisoformat(args.as_of_date) if args.as_of_date else datetime.now(timezone.utc).date()
    repository = EODRepository(Database(Path(args.db_path)))
    bars_by_symbol = {}
    for symbol in repository.get_all_symbols():
        records = repository.get_records(symbol=symbol, to_date=as_of.isoformat())
        if records:
            print(f"[Local EOD D1] {symbol} ({len(records)} bars)", file=sys.stderr)
            bars_by_symbol[symbol] = records
    if not bars_by_symbol:
        raise RuntimeError("No Local EOD D1 data available")
    return scan_d1_linear(
        bars_by_symbol,
        as_of,
        policy=ScannerPolicy(history_window=max(2, int(args.history_window))),
        capital=float(args.capital),
    )


def _write_payload(payload: dict[str, object], output: str) -> None:
    path = Path(output).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        payload = run_advisor(args)
        _write_payload(payload, args.output)
        config = load_dashboard_publisher_config(Path(args.output).resolve().parent)
        result = publish_stock_advisory(payload, config)
        print(f"[DASHBOARD] Stock advisor: {'pushed' if result.pushed else result.status}", file=sys.stderr)
        return 0
    except (OSError, ValueError, RuntimeError) as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
