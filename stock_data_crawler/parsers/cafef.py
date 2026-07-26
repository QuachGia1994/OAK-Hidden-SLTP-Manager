"""CafeF parser — company profile and foreign trading data."""
from __future__ import annotations

import logging
import re
from typing import Any

from stock_data_crawler.models import StockProfile, ForeignData, ForeignTrade, utcnow_iso
from stock_data_crawler.http_client import fetch_html, escape_html_text

logger = logging.getLogger("stock_data_crawler")

# CafeF URL pattern requires slug. We use search page instead.
_CAFEF_SEARCH = "https://s.cafef.vn/screener.aspx?symbol={symbol}"


def _extract_text(html: str, pattern: str) -> str:
    m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    return escape_html_text(m.group(1).strip()) if m else ""


def parse_profile(html: str, symbol: str) -> StockProfile | None:
    """Parse CafeF HTML to extract company profile."""
    name = _extract_text(html, r"<title>\s*([^<:]+)")
    if not name or "Không tìm" in name:
        return None

    # Try to extract exchange from page content
    exchange = ""
    if re.search(r"HOSE|HSX", html, re.IGNORECASE):
        exchange = "HOSE"
    elif re.search(r"HNX", html, re.IGNORECASE):
        exchange = "HNX"
    elif re.search(r"UPCoM|UPCOM", html, re.IGNORECASE):
        exchange = "UPCOM"

    # Try market cap
    market_cap = 0
    cap_match = re.search(r"V[ốơ]n\s*ho[aá][=:]\s*([\d.,]+)\s*(t[yỷ]|tri[eệ]u|ngh[ìi]n)", html, re.IGNORECASE)
    if cap_match:
        val = float(cap_match.group(1).replace(",", "").replace(".", ""))
        unit = cap_match.group(2).lower()
        if "tỷ" in unit or "ty" in unit:
            market_cap = val * 1e9
        elif "nghìn" in unit:
            market_cap = val * 1e6

    return StockProfile(
        symbol=symbol,
        name=name.split("-")[0].strip() if "-" in name else name.strip(),
        exchange=exchange,
        market_cap=market_cap,
        source="CafeF",
        source_url=_CAFEF_SEARCH.format(symbol=symbol),
        fetched_at=utcnow_iso(),
    )


def fetch_profile(symbol: str) -> StockProfile | None:
    """Fetch company profile from CafeF."""
    url = _CAFEF_SEARCH.format(symbol=symbol)
    html = fetch_html(url)
    if not html:
        return None
    return parse_profile(html, symbol)


def fetch_foreign_trading(symbol: str) -> ForeignData | None:
    """Fetch foreign trading data from CafeF."""
    url = _CAFEF_SEARCH.format(symbol=symbol)
    html = fetch_html(url)
    if not html:
        return None
    return parse_foreign_trading(html, symbol)


def parse_foreign_trading(html: str, symbol: str) -> ForeignData | None:
    """Parse CafeF foreign trading data from HTML."""
    # Look for foreign ownership percentage
    ratio = 0
    ratio_match = re.search(r"s[ốơ]\s*h[ữuư]\s*n[ưư][ớợ]c\s*ngo[aà]i[:\s]*([\d.,]+)%", html, re.IGNORECASE)
    if ratio_match:
        ratio = float(ratio_match.group(1).replace(",", "."))

    trades: list[ForeignTrade] = []
    # Parse recent foreign trading rows (simplified)
    rows = re.findall(
        r"(\d{2}/\d{2}/\d{4})\s*[\d.,]+\s*[\d.,]+\s*([\d.,]+)\s*([\d.,]+)",
        html,
    )
    for date_str, buy_vol, sell_vol in rows[:10]:
        try:
            trades.append(ForeignTrade(
                date=date_str,
                buyVol=float(buy_vol.replace(",", "")),
                sellVol=float(sell_vol.replace(",", "")),
            ))
        except (ValueError, IndexError):
            continue

    if not trades and ratio == 0:
        return None

    return ForeignData(
        symbol=symbol,
        foreign_ratio=ratio,
        recent_trades=trades,
        source="CafeF",
        source_url=_CAFEF_SEARCH.format(symbol=symbol),
        fetched_at=utcnow_iso(),
    )
