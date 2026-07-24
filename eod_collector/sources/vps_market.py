"""VPS TradingView Public Market Data Source — HOSE, HNX, UPCoM.

Fetches real daily OHLCV data from the public VPS TradingView history endpoint.
No API key required. Covers all three Vietnamese stock exchanges.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from eod_collector.sources.base import EODDataSource, RawFetchResult
from eod_collector.sources.http_client import fetch_url

logger = logging.getLogger("eod_collector")

# VPS TradingView public endpoint — works for HOSE, HNX, UPCoM symbols
_VPS_BASE_URL = "https://histdatafeed.vps.com.vn/tradingview/history"

# HOSE VN30 + Top Midcaps
HOSE_SYMBOLS = [
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
    "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE",
    "DGC", "DCM", "DPM", "DIG", "DXG", "FRT", "GEX", "HCM", "KBC", "KDH",
    "LPB", "NLG", "NVL", "PC1", "PDR", "PLX", "PNJ", "PVD", "PVT", "REE",
    "SBT", "VCI", "VCS", "VGC", "VHC", "VND",
]

# HNX Top Liquidity
HNX_SYMBOLS = [
    "BSI", "CEO", "IDC", "MBS", "NTP", "PVC", "PVS", "SHS", "TNG", "VGS",
]

# UPCoM Top Liquidity
UPCOM_SYMBOLS = [
    "ACV", "BSR", "C4G", "DDV", "MCH", "MSR", "OIL", "QNS", "VEA", "VGT",
]

ALL_VN_SYMBOLS = HOSE_SYMBOLS + HNX_SYMBOLS + UPCOM_SYMBOLS


def _date_to_ts(d: date) -> int:
    """Convert a date to a UTC unix timestamp (start of day)."""
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def fetch_vps_history(
    symbol: str,
    from_date: date,
    to_date: date,
    *,
    timeout_seconds: int = 12,
    max_retries: int = 2,
) -> list[dict[str, Any]]:
    """Fetch real daily OHLCV rows from VPS for one symbol.

    Returns a list of dicts with keys:
        date (str YYYY-MM-DD), symbol, open, high, low, close, volume, value, source
    """
    # VPS TradingView API requires a lookback window (minimum ~5-7 days) to return data
    req_from_date = from_date - timedelta(days=7)
    from_ts = _date_to_ts(req_from_date)
    to_ts = _date_to_ts(to_date) + 86400  # inclusive end
    url = f"{_VPS_BASE_URL}?symbol={symbol}&resolution=D&from={from_ts}&to={to_ts}"

    content, status_code, _ = fetch_url(url, timeout_seconds=timeout_seconds, max_retries=max_retries)
    if status_code != 200 or not content:
        logger.warning("VPS fetch failed for %s (status %s)", symbol, status_code)
        return []

    try:
        payload = json.loads(content) if isinstance(content, (str, bytes)) else {}
    except (json.JSONDecodeError, ValueError):
        logger.warning("VPS parse error for %s", symbol)
        return []

    if payload.get("s") != "ok":
        logger.debug("VPS no data for %s: status=%s", symbol, payload.get("s"))
        return []

    timestamps = payload.get("t") or []
    opens      = payload.get("o") or []
    highs      = payload.get("h") or []
    lows       = payload.get("l") or []
    closes     = payload.get("c") or []
    volumes    = payload.get("v") or []

    from_str = from_date.strftime("%Y-%m-%d")
    to_str = to_date.strftime("%Y-%m-%d")

    rows: list[dict[str, Any]] = []
    for i, ts in enumerate(timestamps):
        try:
            trading_date_dt = datetime.fromtimestamp(int(ts), tz=timezone.utc).date()
            trading_date = trading_date_dt.strftime("%Y-%m-%d")

            # Filter to requested date window
            if trading_date < from_str or trading_date > to_str:
                continue

            close_price  = float(closes[i])
            open_price   = float(opens[i])  if i < len(opens)   else close_price
            high_price   = float(highs[i])  if i < len(highs)   else close_price
            low_price    = float(lows[i])   if i < len(lows)    else close_price
            volume       = float(volumes[i]) if i < len(volumes) else 0.0
            value        = close_price * volume * 1000.0
            rows.append({
                "date":            trading_date,
                "symbol":          symbol.upper(),
                "exchange":        _guess_exchange(symbol),
                "open":            open_price,
                "high":            high_price,
                "low":             low_price,
                "close":           close_price,
                "reference_price": open_price,
                "ceiling_price":   round(open_price * 1.07, 3),
                "floor_price":     round(open_price * 0.93, 3),
                "volume":          volume,
                "value":           value,
                "source":          "VPS_PUBLIC",
            })
        except (IndexError, TypeError, ValueError) as err:
            logger.debug("VPS row parse error for %s at index %d: %s", symbol, i, err)
            continue

    return rows


def _guess_exchange(symbol: str) -> str:
    sym = symbol.upper()
    if sym in HNX_SYMBOLS:
        return "HNX"
    if sym in UPCOM_SYMBOLS:
        return "UPCOM"
    return "HOSE"


class VPSMarketDataSource(EODDataSource):
    """Unified EOD data source for HOSE, HNX and UPCoM via VPS public API.

    Replaces the synthetic HOSE/HNX/UPCoM fallback with real price data.
    """

    def __init__(self, symbols: list[str] | None = None, rate_limit_seconds: float = 0.15) -> None:
        self.symbols = symbols or ALL_VN_SYMBOLS
        self.rate_limit_seconds = rate_limit_seconds
        self._last_fetch_time: float = 0.0

    @property
    def exchange_name(self) -> str:
        return "VN_ALL"

    def fetch(self, trading_date: date) -> RawFetchResult:
        """Fetch one day's EOD for all symbols, rate-limited to avoid throttling."""
        rows: list[dict[str, Any]] = []
        for symbol in self.symbols:
            # Rate-limit between requests
            elapsed = time.monotonic() - self._last_fetch_time
            if elapsed < self.rate_limit_seconds:
                time.sleep(self.rate_limit_seconds - elapsed)

            day_rows = fetch_vps_history(symbol, trading_date, trading_date)
            rows.extend(day_rows)
            self._last_fetch_time = time.monotonic()

        content = json.dumps(rows, ensure_ascii=False).encode("utf-8")
        return RawFetchResult.create(
            content=content,
            status_code=200 if rows else 204,
            content_type="application/json",
            source_url=_VPS_BASE_URL,
        )

    def parse(self, raw_data: bytes | str) -> list[dict[str, Any]]:
        text = raw_data.decode("utf-8") if isinstance(raw_data, bytes) else raw_data
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, ValueError):
            return []
