"""CafeF parser — company profile, foreign trading, and dividends via JSON API."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from stock_data_crawler.models import (
    StockProfile, ForeignData, ForeignTrade, DividendData, DividendEntry, utcnow_iso,
)
from stock_data_crawler.http_client import fetch_html, fetch_json, escape_html_text

logger = logging.getLogger("stock_data_crawler")

_CAFEF_SEARCH = "https://cafef.vn/du-lieu/screener.aspx?symbol={symbol}"
_CAFEF_REALTIME = "https://cafef.vn/du-lieu/Ajax/PageNew/RealtimePrice.ashx?Symbol={symbol}"
_CAFEF_DIVIDEND = "https://cafef.vn/du-lieu/Ajax/PageNew/LichSuKien.ashx?Symbol={symbol}"


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
    """Fetch foreign trading data from CafeF RealtimePrice JSON API."""
    url = _CAFEF_REALTIME.format(symbol=symbol)
    data = fetch_json(url)
    if not data or not data.get("Success"):
        return None

    d = data.get("Data", {})
    room = d.get("RoomConLai", 0) or 0
    buy_vol = d.get("KhoiLuongNNMua", 0) or 0
    sell_vol = d.get("KhoiLuongNNBan", 0) or 0

    trades: list[ForeignTrade] = []
    if buy_vol or sell_vol:
        trades.append(ForeignTrade(
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            buyVol=buy_vol,
            sellVol=sell_vol,
        ))

    return ForeignData(
        symbol=symbol,
        foreign_ratio=room,
        recent_trades=trades,
        source="CafeF",
        source_url=_CAFEF_REALTIME.format(symbol=symbol),
        fetched_at=utcnow_iso(),
    )


def fetch_dividends(symbol: str) -> DividendData | None:
    """Fetch dividend history from CafeF LichSuKien JSON API."""
    url = _CAFEF_DIVIDEND.format(symbol=symbol)
    data = fetch_json(url)
    if not data or not data.get("Success"):
        return None

    items = data.get("Data", [])
    if not items:
        return None

    dividends: list[DividendEntry] = []
    for item in items[:20]:
        # Parse date from /Date(ms)/ format
        time_str = item.get("Time", "")
        date_match = re.search(r"/Date\((\d+)\)/", time_str)
        if not date_match:
            continue
        ts = int(date_match.group(1)) / 1000
        ex_date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

        cash_amount = 0.0
        stock_ratio = 0.0
        for text in item.get("Text", []):
            text = text.lower()
            # "Cổ tức bằng Tiền, tỷ lệ 5%"
            cash_match = re.search(r"ti[eề]n.*?t[yỷ]\s*l[eệ]\s*([\d.]+)%", text)
            if cash_match:
                cash_amount = float(cash_match.group(1))
            # "Cổ tức bằng Cổ phiếu, tỷ lệ 100:10"
            stock_match = re.search(r"c[oổ]\s*phi[eế]u.*?t[yỷ]\s*l[eệ]\s*(\d+):(\d+)", text)
            if stock_match:
                old = float(stock_match.group(1))
                new = float(stock_match.group(2))
                stock_ratio = (new / old * 100) if old > 0 else 0

        if cash_amount > 0 or stock_ratio > 0:
            dividends.append(DividendEntry(
                ex_date=ex_date,
                pay_date="",
                cash_amount=cash_amount,
                stock_ratio=stock_ratio,
                source="CafeF",
                source_url=_CAFEF_DIVIDEND.format(symbol=symbol),
            ))

    if not dividends:
        return None

    return DividendData(
        symbol=symbol,
        dividends=dividends,
        source="CafeF",
        source_url=_CAFEF_DIVIDEND.format(symbol=symbol),
        fetched_at=utcnow_iso(),
    )


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
