"""TCBS free API client for Vietnamese stock fundamental data.

No authentication required. Data sourced from apipubaws.tcbs.com.vn.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

logger = logging.getLogger("tcbs_stock_data")

_BASE = "https://apipubaws.tcbs.com.vn/stock-insight"
_TIMEOUT = 10


def _get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{_BASE}{path}"
    try:
        resp = requests.get(url, params=params, timeout=_TIMEOUT, headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        })
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.warning("TCBS fetch error %s: %s", url, exc)
        return None


def fetch_company_overview(symbol: str) -> dict[str, Any] | None:
    """Return company overview: name, exchange, market_cap, industry, etc."""
    data = _get(f"/v1/stock/{symbol.upper()}/overview")
    if not data:
        return None
    d = data.get("data", data)
    if isinstance(d, list) and d:
        d = d[0]
    return {
        "symbol": symbol.upper(),
        "name": d.get("companyName", d.get("name", "")),
        "exchange": d.get("exchange", ""),
        "industry": d.get("industry", ""),
        "market_cap": d.get("marketCap", 0),
        "market_cap_display": _format_cap(d.get("marketCap", 0)),
        "ceo": d.get("ceo", ""),
        "website": d.get("website", ""),
        "charter_capital": d.get("charterCapital", 0),
        "outstanding_shares": d.get("outstandingShares", 0),
        "shares_float": d.get("sharesFloat", 0),
        "foreign_ownership_pct": d.get("foreignOwnershipLimit", 0),
        "psr": d.get("psr", 0),
        "pe": d.get("pe", 0),
        "pb": d.get("pb", 0),
        "roe": d.get("roe", 0),
        "eps": d.get("eps", 0),
    }


def fetch_financial_statements(symbol: str) -> list[dict[str, Any]]:
    """Return last 4 quarters of financial data: revenue, LNST, EPS, ROE."""
    data = _get(f"/v1/stock/{symbol.upper()}/financial-declaration")
    if not data:
        return []
    items = data.get("data", data)
    if not isinstance(items, list):
        return []
    results = []
    for item in items[:8]:
        results.append({
            "period": item.get("period", ""),
            "quarter": item.get("quarter", ""),
            "year": item.get("year", ""),
            "revenue": item.get("revenue", 0),
            "revenue_yoy": item.get("revenueYoy", 0),
            "net_profit": item.get("netProfit", 0),
            "net_profit_yoy": item.get("netProfitYoy", 0),
            "eps": item.get("eps", 0),
            "roe": item.get("roe", 0),
            "roa": item.get("roa", 0),
            "pe": item.get("pe", 0),
            "pb": item.get("pb", 0),
        })
    return results[:4]


def fetch_dividend_history(symbol: str) -> list[dict[str, Any]]:
    """Return dividend payment history."""
    data = _get(f"/v2/stock/{symbol.upper()}/dividend-history")
    if not data:
        return []
    items = data.get("data", data)
    if not isinstance(items, list):
        return []
    results = []
    for item in items[:10]:
        results.append({
            "ex_date": item.get("exDividendDate", item.get("exDate", "")),
            "cash_dividend": item.get("cashDividend", item.get("dividendPerShare", 0)),
            "stock_dividend": item.get("stockDividend", 0),
            "ratio": item.get("ratio", ""),
        })
    return results


def fetch_foreign_ownership(symbol: str) -> dict[str, Any]:
    """Return foreign ownership ratio and recent trading data."""
    data = _get(f"/v1/stock/{symbol.upper()}/ownership")
    if not data:
        return {"foreign_ratio": 0, "foreign_buy_volume": 0, "foreign_sell_volume": 0}
    d = data.get("data", data)
    if isinstance(d, list) and d:
        d = d[0]
    return {
        "foreign_ratio": d.get("foreignOwnershipRatio", d.get("foreignPercent", 0)),
        "foreign_buy_volume": d.get("foreignBuyVolume", 0),
        "foreign_sell_volume": d.get("foreignSellVolume", 0),
    }


def fetch_all(symbol: str) -> dict[str, Any]:
    """Fetch all data for a symbol and return combined dict."""
    symbol = symbol.upper()
    overview = fetch_company_overview(symbol) or {}
    financials = fetch_financial_statements(symbol)
    dividends = fetch_dividend_history(symbol)
    foreign = fetch_foreign_ownership(symbol)

    return {
        "symbol": symbol,
        "overview": overview,
        "financials": financials,
        "dividends": dividends,
        "foreign": foreign,
    }


def _format_cap(value: float) -> str:
    """Format market cap value to Vietnamese display string."""
    if not value:
        return "N/A"
    if value >= 1_000_000_000_000:
        return f"{value / 1_000_000_000_000:,.1f} nghìn tỷ"
    if value >= 1_000_000_000:
        return f"{value / 1_000_000_000:,.0f} tỷ"
    if value >= 1_000_000:
        return f"{value / 1_000_000:,.0f} triệu"
    return f"{value:,.0f}"
