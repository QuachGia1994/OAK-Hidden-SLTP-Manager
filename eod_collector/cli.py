"""CLI entry point for Local EOD Market Data Collector."""
from __future__ import annotations

import argparse
from datetime import date, datetime
import logging
from pathlib import Path
import sys
from typing import Sequence

from eod_collector.config import Config
from eod_collector.services.collector import CollectorService

# Setup rotating file log as required by PDF (page 6)
def _setup_logging() -> None:
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "eod_collector.log"

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="eod_collector",
        description="Local EOD Market Data Collector for Vietnam Stock Exchanges (HOSE, HNX, UPCoM)",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # update
    p_update = subparsers.add_parser("update", help="Update market data for today or specified date")
    p_update.add_argument("--date", help="Target date YYYY-MM-DD")

    # backfill
    p_backfill = subparsers.add_parser("backfill", help="Backfill historical EOD market data")
    p_backfill.add_argument("--days", type=int, help="Number of historical days to backfill")
    p_backfill.add_argument("--from", dest="from_date", help="Start date YYYY-MM-DD")
    p_backfill.add_argument("--to", dest="to_date", help="End date YYYY-MM-DD")

    # validate
    p_val = subparsers.add_parser("validate", help="Validate stored database records")
    p_val.add_argument("--date", help="Validation target date YYYY-MM-DD")

    # status
    subparsers.add_parser("status", help="Show database collection status and health diagnostics")

    # export
    p_exp = subparsers.add_parser("export", help="Export EOD prices to CSV")
    p_exp.add_argument("--symbol", help="Stock symbol to export")
    p_exp.add_argument("--exchange", help="Exchange to export (HOSE, HNX, UPCOM)")
    p_exp.add_argument("--output", help="Output file path (default: data/export.csv)")

    # import-file
    p_imp = subparsers.add_parser("import-file", help="Manually import a CSV/XLSX EOD file")
    p_imp.add_argument("file_path", help="Path to raw file")
    p_imp.add_argument("--exchange", required=True, help="Exchange name (HOSE, HNX, UPCOM)")
    p_imp.add_argument("--date", help="Trading date YYYY-MM-DD override")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    _setup_logging()
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    config = Config.load()
    service = CollectorService(config)

    try:
        if args.command == "update":
            d = _parse_date(args.date) if args.date else None
            res = service.update(trading_date=d)
            print(f"[EOD_COLLECTOR] Update complete: {res}")
            return 0

        elif args.command == "backfill":
            f_d = _parse_date(args.from_date) if args.from_date else None
            t_d = _parse_date(args.to_date) if args.to_date else None
            res = service.backfill(days=args.days, from_date=f_d, to_date=t_d)
            print(f"[EOD_COLLECTOR] Backfill complete: {res}")
            return 0

        elif args.command == "validate":
            d = _parse_date(args.date) if args.date else None
            warnings = service.validate(trading_date=d)
            print(f"[EOD_COLLECTOR] Validation report for {d or 'latest'}:")
            for ex, w_list in warnings.items():
                if w_list:
                    print(f"  [{ex}] {len(w_list)} warnings/errors:")
                    for w in w_list:
                        print(f"    - {w}")
                else:
                    print(f"  [{ex}] OK (0 issues)")
            return 0

        elif args.command == "status":
            st = service.status()
            print("=== LOCAL EOD MARKET DATA STATUS ===")
            print(f"• Latest Trading Date in DB : {st['latest_date']}")
            print("• Symbol Count by Exchange  :")
            for ex, cnt in st['symbol_counts_by_exchange'].items():
                print(f"    - {ex}: {cnt} symbols")
            print(f"• Saved Trading Sessions    : {st['saved_sessions_count']} dates")
            print(f"• Active Data Sources       : {', '.join(st['active_sources'])}")
            if st['missing_dates']:
                print(f"• Missing Recent Dates ({len(st['missing_dates'])}): {', '.join(st['missing_dates'][:5])}...")
            else:
                print("• Missing Recent Dates      : None (up to date)")
            return 0

        elif args.command == "export":
            out_file = service.export(symbol=args.symbol, exchange=args.exchange, output_path=args.output)
            print(f"[EOD_COLLECTOR] Data exported to {out_file}")
            return 0

        elif args.command == "import-file":
            d = _parse_date(args.date) if args.date else None
            count = service.import_file(args.file_path, exchange=args.exchange, trading_date=d)
            print(f"[EOD_COLLECTOR] Imported {count} records from {args.file_path}")
            return 0

    except Exception as error:
        print(f"[ERROR] {error}", file=sys.stderr)
        logging.exception("CLI command execution failed: %s", error)
        return 2

    return 0


def _parse_date(val: str) -> date:
    try:
        return datetime.strptime(val.strip(), "%Y-%m-%d").date()
    except ValueError as err:
        raise ValueError(f"Invalid date string '{val}', expected format YYYY-MM-DD") from err


if __name__ == "__main__":
    sys.exit(main())
