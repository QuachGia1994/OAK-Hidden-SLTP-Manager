"""Read-only Local EOD market-data provider for the stock scanner.

Falls back to real VPS public API data when symbols are missing from local DB.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
from typing import Sequence

from domain.stock_scanner import AfternoonPoint
from eod_collector.config import Config
from eod_collector.models import EODRecord
from eod_collector.services.collector import CollectorService
from eod_collector.sources.vps_market import (
    ALL_VN_SYMBOLS,
    HOSE_SYMBOLS,
    HNX_SYMBOLS,
    UPCOM_SYMBOLS,
    fetch_vps_history,
)

logger = logging.getLogger("eod_collector")

# Legacy alias so other callers don't break
VN30_CONSTITUENTS = [
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
    "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE",
]

# All constituents available for scanning
ALL_EXCHANGE_CONSTITUENTS = ALL_VN_SYMBOLS

BASE_PRICES = {
    "FPT": 125.0, "HPG": 28.5, "VCB": 92.0, "VHM": 42.0, "VIC": 45.0,
    "VNM": 68.0, "MSN": 75.0, "MWG": 62.0, "TCB": 48.0, "STB": 31.0,
    "MBB": 24.0, "ACB": 25.5, "BID": 49.0, "CTG": 35.0, "GAS": 78.0,
    "GVR": 34.0, "HDB": 23.5, "PLX": 38.0, "POW": 12.5, "SAB": 58.0,
    "SHB": 11.5, "SSB": 22.0, "SSI": 36.0, "TPB": 18.5, "VIB": 21.5,
    "VJC": 105.0, "VPB": 19.5, "VRE": 22.5, "BCM": 65.0, "BVH": 41.0,
}


class LocalEODMarketDataProvider:
    """Market data provider sourcing EOD prices from local SQLite DB or VPS API.

    Priority order for get_afternoon_points:
      1. Local SQLite DB records (UPSERTED by eod_collector update)
      2. Live VPS public API fetch → cache into DB for next time
    """

    def __init__(self, collector_service: CollectorService | None = None) -> None:
        self.service = collector_service or CollectorService(Config.load())

    def __enter__(self) -> LocalEODMarketDataProvider:
        return self

    def __exit__(self, *_: object) -> None:
        pass

    def get_vn30_symbols(self) -> list[str]:
        """Return constituent symbols across HOSE, HNX, UPCoM for scanning."""
        db_symbols = self.service.repository.get_all_symbols()
        if db_symbols:
            return sorted(set(db_symbols).union(ALL_EXCHANGE_CONSTITUENTS))
        return list(ALL_EXCHANGE_CONSTITUENTS)

    def has_trading_session(self, trading_date: date) -> bool:
        """Return whether local DB or market calendar reports session for the date."""
        if trading_date.weekday() in (5, 6):
            return False
        date_str = trading_date.strftime("%Y-%m-%d")
        if date_str in self.service.config.collector.holidays:
            return False
        return True

    def get_afternoon_points(self, symbol: str, from_date: date, to_date: date) -> list[AfternoonPoint]:
        """Return historical executable EOD points for symbol.

        1. Try local SQLite DB first.
        2. If missing or stale, fetch from VPS public API and cache into DB.
        """
        from_str = from_date.strftime("%Y-%m-%d")
        to_str = to_date.strftime("%Y-%m-%d")

        records = self.service.repository.get_records(
            symbol=symbol,
            from_date=from_str,
            to_date=to_str,
        )

        # Check if records have real (varied) prices or are flat synthetic placeholders
        if not records or _is_synthetic_data(records):
            logger.info("Fetching real VPS data for %s (%s → %s)", symbol, from_str, to_str)
            self._fetch_and_cache_vps(symbol, from_date, to_date)
            records = self.service.repository.get_records(
                symbol=symbol,
                from_date=from_str,
                to_date=to_str,
            )

        points: list[AfternoonPoint] = []
        for r in records:
            try:
                d = datetime.strptime(r.date, "%Y-%m-%d").date()
                price = float(r.close)
                val = float(r.value)
                if price > 0:
                    points.append(AfternoonPoint(trading_date=d, price=price, matched_value=val))
            except Exception:
                continue
        return points

    def _fetch_and_cache_vps(self, symbol: str, from_date: date, to_date: date) -> None:
        """Fetch real OHLCV data from VPS API and upsert into local DB."""
        try:
            rows = fetch_vps_history(symbol, from_date, to_date)
        except Exception as err:
            logger.warning("VPS fetch error for %s: %s", symbol, err)
            return

        if not rows:
            logger.debug("No VPS data returned for %s", symbol)
            return

        eod_records: list[EODRecord] = []
        for row in rows:
            try:
                eod_records.append(
                    EODRecord(
                        date=row["date"],
                        symbol=row["symbol"],
                        exchange=row.get("exchange", "HOSE"),
                        open=float(row.get("open", 0)),
                        high=float(row.get("high", 0)),
                        low=float(row.get("low", 0)),
                        close=float(row.get("close", 0)),
                        reference_price=float(row.get("reference_price", row.get("open", 0))),
                        ceiling_price=float(row.get("ceiling_price", 0)),
                        floor_price=float(row.get("floor_price", 0)),
                        volume=float(row.get("volume", 0)),
                        value=float(row.get("value", 0)),
                        source=row.get("source", "VPS_PUBLIC"),
                    )
                )
            except (KeyError, TypeError, ValueError) as err:
                logger.debug("Row parse error for %s: %s", symbol, err)
                continue

        if eod_records:
            saved = self.service.repository.upsert_records(eod_records)
            logger.info("Cached %d VPS records for %s into local DB", saved, symbol)


def _is_synthetic_data(records: Sequence[EODRecord]) -> bool:
    """Return True if records appear to be synthetic placeholders.

    Detects:
    - Records from known synthetic sources (LOCAL_EOD_DB, HOSE_OFFICIAL_PUBLIC)
    - All prices identical (flat)
    - All successive price diffs are identical (linear ramp from _ensure_synthetic_history)
    """
    if not records:
        return True

    # Check source field — any synthetic source → refresh
    synthetic_sources = {"LOCAL_EOD_DB", "HOSE_OFFICIAL_PUBLIC", "HNX_OFFICIAL_PUBLIC", "UPCOM_OFFICIAL_PUBLIC"}
    if any(getattr(r, "source", "") in synthetic_sources for r in records):
        return True

    closes = [float(r.close) for r in records if r.close]
    if len(closes) < 3:
        return False

    # Flat check
    if max(closes) == min(closes):
        return True

    # Linear ramp check: all successive differences identical (synthetic 0.15/step pattern)
    diffs = [round(closes[i + 1] - closes[i], 4) for i in range(len(closes) - 1)]
    if len(set(diffs)) <= 2 and len(diffs) >= 5:
        # All diffs are the same (or two values due to rounding at breakpoints)
        return True

    return False
