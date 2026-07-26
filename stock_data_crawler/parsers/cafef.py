"""CafeF parser — company profile, ownership, dividends, financial indicators via JSON API."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from stock_data_crawler.models import (
    StockProfile, ForeignData, ForeignTrade, DividendData, DividendEntry,
    FinancialData, FinancialIndicator, TopShareholder, utcnow_iso,
)
from stock_data_crawler.http_client import fetch_html, fetch_json, escape_html_text

logger = logging.getLogger("stock_data_crawler")

_CAFEF_SEARCH = "https://cafef.vn/du-lieu/screener.aspx?symbol={symbol}"
_CAFEF_REALTIME = "https://cafef.vn/du-lieu/Ajax/PageNew/RealtimePrice.ashx?Symbol={symbol}"
_CAFEF_DIVIDEND = "https://cafef.vn/du-lieu/Ajax/PageNew/LichSuKien.ashx?Symbol={symbol}"
_CAFEF_OWNERSHIP = "https://cafef.vn/du-lieu/Ajax/PageNew/CoCauSoHuu.ashx?Symbol={symbol}"
_CAFEF_INDICATORS = "https://cafef.vn/du-lieu/Ajax/PageNew/ChiSoTaiChinh.ashx?Symbol={symbol}"
_CAFEF_HEADER = "https://cafef.vn/du-lieu/Ajax/PageNew/PriceRealTimeHeader.ashx?Symbol={symbol}"

# MaSan codes from CafeF PriceRealTimeHeader
_EXCHANGE_MAP = {1: "HOSE", 2: "HNX", 3: "UPCOM"}


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

    # Try market cap from HTML
    market_cap = 0
    cap_match = re.search(r"V[ốơ]n\s*ho[aá][=:]\s*([\d.,]+)\s*(t[yỷ]|tri[eệ]u|ngh[ìi]n)", html, re.IGNORECASE)
    if cap_match:
        val = float(cap_match.group(1).replace(",", "").replace(".", ""))
        unit = cap_match.group(2).lower()
        if "tỷ" in unit or "ty" in unit:
            market_cap = val * 1e9
        elif "nghìn" in unit:
            market_cap = val * 1e6

    # Try to extract industry from screener page
    industry = ""
    ind_match = re.search(r"Ng[aà]nh[^>]*>([^<]+)", html, re.IGNORECASE)
    if ind_match:
        industry = escape_html_text(ind_match.group(1).strip())

    return StockProfile(
        symbol=symbol,
        name=name.split("-")[0].strip() if "-" in name else name.strip(),
        exchange=exchange,
        industry=industry,
        market_cap=market_cap,
        source="CafeF",
        source_url=_CAFEF_SEARCH.format(symbol=symbol),
        fetched_at=utcnow_iso(),
    )


def fetch_profile(symbol: str) -> StockProfile | None:
    """Fetch company profile from CafeF, enriched with PriceRealTimeHeader and ChiSoTaiChinh."""
    url = _CAFEF_SEARCH.format(symbol=symbol)
    html = fetch_html(url)
    profile = parse_profile(html, symbol) if html else None

    if not profile:
        profile = StockProfile(
            symbol=symbol,
            name=symbol,
            exchange="",
            industry="",
            market_cap=0,
            source="CafeF",
            source_url=_CAFEF_SEARCH.format(symbol=symbol),
            fetched_at=utcnow_iso(),
        )

    # Enrich exchange from PriceRealTimeHeader (more reliable than HTML)
    header_data = fetch_json(_CAFEF_HEADER.format(symbol=symbol))
    if header_data and header_data.get("Success"):
        ma_san = header_data.get("Data", {}).get("MaSan", 0)
        if ma_san in _EXCHANGE_MAP:
            profile.exchange = _EXCHANGE_MAP[ma_san]

    # Enrich market cap from ChiSoTaiChinh (more reliable than HTML)
    indicators = fetch_indicators(symbol)
    if indicators and indicators.market_cap > 0:
        profile.market_cap = indicators.market_cap

    return profile


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


def _clean_html_name(text: str) -> str:
    """Strip HTML tags from shareholder name (CafeF returns <a> tags)."""
    text = re.sub(r"<[^>]+>", "", text).strip()
    return escape_html_text(text) if text else ""


def _parse_ratio(val: Any) -> float:
    """Parse Vietnamese-formatted ratio like '5,51' → 5.51."""
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(",", ".").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def fetch_ownership(symbol: str) -> ForeignData | None:
    """Fetch ownership structure from CafeF CoCauSoHuu JSON API.

    Returns ForeignData with:
    - foreign_ratio: NuocNgoai % (actual foreign ownership)
    - state_ratio: NhaNuoc % (state ownership)
    - institutional_ratio: sum of CORP_ shareholders %
    - management_ratio: sum of CEO_ shareholders %
    - top_shareholders: list of top shareholders with type classification
    """
    url = _CAFEF_OWNERSHIP.format(symbol=symbol)
    data = fetch_json(url)
    if not data or not data.get("Success"):
        return None

    d = data.get("Data", {})
    if not isinstance(d, dict):
        return None

    foreign_ratio = float(d.get("NuocNgoai", 0) or 0)
    state_ratio = float(d.get("NhaNuoc", 0) or 0)

    shareholders_raw = d.get("CoDongSoHuu", [])
    institutional_total = 0.0
    management_total = 0.0

    # Build deduplicated map: merge same-name shareholders, keep strongest type
    name_map: dict[str, TopShareholder] = {}
    for sh in shareholders_raw:
        code = str(sh.get("Code", ""))
        name = _clean_html_name(str(sh.get("Name", "")))
        ratio = _parse_ratio(sh.get("AssetRate", 0))

        if not name or ratio <= 0:
            continue

        # Determine type: CEO_ → BLĐ, CORP_ → TC, else → TN
        if code.startswith("CEO_"):
            sh_type = "BLĐ"
            management_total += ratio
        elif code.startswith("CORP_"):
            sh_type = "TC"
            institutional_total += ratio
        else:
            sh_type = "TN"

        # Merge if same name already exists — sum ratios, upgrade type priority
        if name in name_map:
            existing = name_map[name]
            existing.ratio += ratio
            # BLĐ > TC > TN — keep the more authoritative type
            if sh_type == "BLĐ" and existing.type != "BLĐ":
                existing.type = "BLĐ"
            elif sh_type == "TC" and existing.type == "TN":
                existing.type = "TC"
        else:
            name_map[name] = TopShareholder(name=name, ratio=ratio, type=sh_type)

    # Sort by ratio descending, take top 10
    top_shareholders = sorted(name_map.values(), key=lambda s: s.ratio, reverse=True)[:10]

    return ForeignData(
        symbol=symbol,
        foreign_ratio=foreign_ratio,
        state_ratio=state_ratio,
        institutional_ratio=institutional_total,
        management_ratio=management_total,
        top_shareholders=top_shareholders,
        source="CafeF",
        source_url=url,
        fetched_at=utcnow_iso(),
    )


def fetch_indicators(symbol: str) -> FinancialData | None:
    """Fetch financial indicators from CafeF ChiSoTaiChinh JSON API.

    Returns market cap, EPS, P/E, P/B, shares outstanding, etc.
    """
    url = _CAFEF_INDICATORS.format(symbol=symbol)
    data = fetch_json(url)
    if not data or not data.get("Success"):
        return None

    items = data.get("Data", [])
    if not items:
        return None

    indicators: list[FinancialIndicator] = []
    market_cap = 0.0
    shares_outstanding = 0.0
    eps = 0.0
    pe_ratio = 0.0
    pb_ratio = 0.0

    for item in items:
        code = str(item.get("Code", ""))
        label = re.sub(r"<[^>]+>", "", str(item.get("Text", ""))).strip()
        value = str(item.get("Value", ""))
        number = int(item.get("Number", 0))

        indicators.append(FinancialIndicator(
            code=code,
            label=label,
            value=value,
            number=number,
        ))

        # Extract key financial metrics
        if code == "VonHoaThiTruong":
            market_cap = _parse_vn_number(value)
        elif code == "EPScoBan":
            try:
                eps = float(value.replace(",", "."))
            except (ValueError, TypeError):
                eps = 0.0
        elif code == "P/E":
            try:
                pe_ratio = float(value.replace(",", "."))
            except (ValueError, TypeError):
                pe_ratio = 0.0
        elif code == "Beta":  # CafeF calls P/B as "Beta" in Code field
            try:
                pb_ratio = float(value.replace(",", "."))
            except (ValueError, TypeError):
                pb_ratio = 0.0
        elif code == "KlcpNY":
            shares_outstanding = _parse_vn_number(value)
        elif code == "KlcpLuuHanh":
            if shares_outstanding == 0:
                shares_outstanding = _parse_vn_number(value)

    return FinancialData(
        symbol=symbol,
        indicators=indicators,
        market_cap=market_cap,
        shares_outstanding=shares_outstanding,
        eps=eps,
        pe_ratio=pe_ratio,
        pb_ratio=pb_ratio,
        source="CafeF",
        source_url=url,
        fetched_at=utcnow_iso(),
    )


def _parse_vn_number(s: str) -> float:
    """Parse Vietnamese-formatted number like '6,364.83' or '172,734,187' → float."""
    s = s.strip()
    # Vietnamese uses comma as thousands separator, dot as decimal
    # But sometimes it's reversed (dot as thousands, comma as decimal)
    # Check pattern: if contains both comma and dot, need to determine format
    if "," in s and "." in s:
        # If comma appears before dot → comma is thousands, dot is decimal
        # e.g., "6,364.83" → 6364.83
        last_comma = s.rfind(",")
        last_dot = s.rfind(".")
        if last_comma < last_dot:
            # comma=thousands, dot=decimal
            return float(s.replace(",", ""))
        else:
            # dot=thousands, comma=decimal (European format)
            return float(s.replace(".", "").replace(",", "."))
    elif "," in s:
        # Only commas: could be thousands separator or decimal
        # e.g., "172,734,187" → 172734187 (thousands)
        # e.g., "5,51" → 5.51 (decimal)
        parts = s.split(",")
        if len(parts) > 2:
            # Multiple commas → thousands separator
            return float(s.replace(",", ""))
        else:
            # Single comma → likely decimal separator
            return float(s.replace(",", "."))
    elif "." in s:
        # Only dots
        parts = s.split(".")
        if len(parts) > 2:
            # Multiple dots → thousands separator
            return float(s.replace(".", ""))
        else:
            # Single dot → decimal
            return float(s)
    else:
        try:
            return float(s)
        except (ValueError, TypeError):
            return 0.0
