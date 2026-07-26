"""Main crawler orchestrator — fetches data for all symbols and writes static JSON."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Sequence

from stock_data_crawler.http_client import validate_symbol
from stock_data_crawler.writer import write_profile, write_reports, write_dividends, write_foreign
from stock_data_crawler.parsers import cafef, vsdc, ssc, hnx_parser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("stock_data_crawler")


def crawl_symbol(symbol: str, output_base: str) -> dict[str, bool]:
    """Crawl all data sources for one symbol. Returns {source: changed}."""
    symbol = symbol.upper().strip()
    if not validate_symbol(symbol):
        logger.warning("Invalid symbol: %s", symbol)
        return {}

    output_dir = os.path.join(output_base, symbol)
    results: dict[str, bool] = {}

    # 1. Profile (CafeF primary, HNX fallback)
    try:
        profile = cafef.fetch_profile(symbol)
        if not profile:
            profile = hnx_parser.fetch_profile(symbol)
        results["profile"] = write_profile(profile, output_dir)
        if not profile:
            logger.info("[%s] No profile data", symbol)
    except Exception as exc:
        logger.error("[%s] Profile error: %s", symbol, exc)
        write_profile(None, output_dir)  # keep stale cache

    # 2. Financial reports (SSC/CafeF primary, HNX fallback)
    try:
        reports = ssc.fetch_reports(symbol)
        if not reports:
            reports = hnx_parser.fetch_reports(symbol)
        results["reports"] = write_reports(reports, output_dir)
        if not reports:
            logger.info("[%s] No reports data", symbol)
    except Exception as exc:
        logger.error("[%s] Reports error: %s", symbol, exc)
        write_reports(None, output_dir)  # keep stale cache

    # 3. Dividends (VSDC primary, HNX fallback)
    try:
        dividends = vsdc.fetch_dividends(symbol)
        if not dividends:
            dividends = hnx_parser.fetch_events(symbol)
        results["dividends"] = write_dividends(dividends, output_dir)
        if not dividends:
            logger.info("[%s] No dividend data", symbol)
    except Exception as exc:
        logger.error("[%s] Dividends error: %s", symbol, exc)
        write_dividends(None, output_dir)  # keep stale cache

    # 4. Foreign trading (CafeF)
    try:
        foreign = cafef.fetch_foreign_trading(symbol)
        results["foreign"] = write_foreign(foreign, output_dir)
        if not foreign:
            logger.info("[%s] No foreign trading data", symbol)
    except Exception as exc:
        logger.error("[%s] Foreign error: %s", symbol, exc)
        write_foreign(None, output_dir)  # keep stale cache

    return results


def load_symbols(symbols_file: str | None, explicit: list[str]) -> list[str]:
    """Load symbol list from file or explicit args."""
    symbols = list(explicit)
    if symbols_file and os.path.exists(symbols_file):
        with open(symbols_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            symbols.extend(str(s).upper() for s in data)
        elif isinstance(data, dict) and "symbols" in data:
            symbols.extend(str(s).upper() for s in data["symbols"])
    return sorted(set(symbols))


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Stock data crawler")
    parser.add_argument("--symbols", nargs="*", default=[], help="Symbols to crawl")
    parser.add_argument("--symbols-file", help="JSON file with symbol list")
    parser.add_argument("--output", default="dashboard/public/stock-data", help="Output directory")
    parser.add_argument("--workers", type=int, default=4, help="Parallel workers")
    parser.add_argument("--limit", type=int, default=0, help="Max symbols (0=all)")
    args = parser.parse_args(argv)

    symbols = load_symbols(args.symbols_file, args.symbols)
    if args.limit > 0:
        symbols = symbols[:args.limit]

    if not symbols:
        logger.error("No symbols to crawl. Use --symbols or --symbols-file.")
        sys.exit(1)

    logger.info("Crawling %d symbols to %s", len(symbols), args.output)
    os.makedirs(args.output, exist_ok=True)

    changed = 0
    errors = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(crawl_symbol, sym, args.output): sym for sym in symbols}
        for future in as_completed(futures):
            sym = futures[future]
            try:
                result = future.result()
                if any(result.values()):
                    changed += 1
                logger.info("[%s] Done: %s", sym, result)
            except Exception as exc:
                errors += 1
                logger.error("[%s] FAILED: %s", sym, exc)

    logger.info("Complete: %d symbols crawled, %d changed, %d errors", len(symbols), changed, errors)


if __name__ == "__main__":
    main()
