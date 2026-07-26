"""HNX parser — company profile, events, and reports from Hanoi Stock Exchange."""
from __future__ import annotations

import logging
import re
from typing import Any

from stock_data_crawler.models import (
    StockProfile,
    ReportData,
    FinancialReport,
    DividendData,
    DividendEntry,
    utcnow_iso,
)
from stock_data_crawler.http_client import fetch_html, escape_html_text

logger = logging.getLogger("stock_data_crawler")

_HNX_URL = "https://www.hnx.vn/co-phieu/{symbol}"
_HNX_EVENTS_URL = "https://www.hnx.vn/su-kien/{symbol}"


def _extract_text(html: str, pattern: str) -> str:
    m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    return escape_html_text(m.group(1).strip()) if m else ""


def parse_profile(html: str, symbol: str) -> StockProfile | None:
    """Parse HNX HTML to extract company profile."""
    name = _extract_text(html, r"<title>\s*([^<:]+)")
    if not name or "Không" in name or "404" in name:
        return None

    # HNX stocks are on HNX or UPCoM
    exchange = "HNX"
    if re.search(r"UPCoM|UPCOM", html, re.IGNORECASE):
        exchange = "UPCOM"

    return StockProfile(
        symbol=symbol,
        name=name.split("-")[0].strip() if "-" in name else name.strip(),
        exchange=exchange,
        source="HNX",
        source_url=_HNX_URL.format(symbol=symbol),
        fetched_at=utcnow_iso(),
    )


def fetch_profile(symbol: str) -> StockProfile | None:
    """Fetch company profile from HNX."""
    url = _HNX_URL.format(symbol=symbol)
    html = fetch_html(url)
    if not html:
        return None
    return parse_profile(html, symbol)


def parse_events(html: str, symbol: str) -> DividendData | None:
    """Parse HNX events page to extract dividends and corporate events."""
    dividends: list[DividendEntry] = []

    # Look for event table rows
    rows = re.findall(
        r"<tr[^>]*>.*?</tr>",
        html,
        re.DOTALL | re.IGNORECASE,
    )

    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
        if len(cells) < 3:
            continue

        # Try to extract dates from cells
        cell_text = " ".join(cells)
        dates = re.findall(r"(\d{2}/\d{2}/\d{4})", cell_text)
        if not dates:
            continue

        ex_date = dates[0]
        pay_date = dates[1] if len(dates) > 1 else ""

        # Look for cash amounts
        cash = 0.0
        cash_match = re.search(r"(\d[\d.,]*)\s*đồng", cell_text, re.IGNORECASE)
        if cash_match:
            try:
                cash = float(cash_match.group(1).replace(".", "").replace(",", "."))
            except (ValueError, TypeError):
                pass

        # Look for stock ratios
        stock = 0.0
        stock_match = re.search(r"(\d+(?:[.,]\d+)?)\s*%", cell_text)
        if stock_match:
            try:
                stock = float(stock_match.group(1).replace(",", "."))
            except (ValueError, TypeError):
                pass

        # Only add if it looks like a dividend event
        if "cổ tức" in cell_text.lower() or cash > 0 or stock > 0:
            dividends.append(DividendEntry(
                ex_date=ex_date,
                pay_date=pay_date,
                cash_amount=cash,
                stock_ratio=stock,
                source="HNX",
                source_url=_HNX_EVENTS_URL.format(symbol=symbol),
            ))

    if not dividends:
        return None

    return DividendData(
        symbol=symbol,
        dividends=dividends[:10],
        source="HNX",
        source_url=_HNX_EVENTS_URL.format(symbol=symbol),
        fetched_at=utcnow_iso(),
    )


def fetch_events(symbol: str) -> DividendData | None:
    """Fetch corporate events from HNX."""
    url = _HNX_EVENTS_URL.format(symbol=symbol)
    html = fetch_html(url)
    if not html:
        return None
    return parse_events(html, symbol)


def parse_reports(html: str, symbol: str) -> ReportData | None:
    """Parse HNX HTML to extract financial report listings."""
    reports: list[FinancialReport] = []

    # Look for PDF links with report context
    pdf_links = re.findall(
        r'<a[^>]*href="([^"]*\.pdf[^"]*)"[^>]*>([^<]+)</a>',
        html,
        re.IGNORECASE,
    )

    for url, title in pdf_links[:10]:
        title = escape_html_text(title.strip())
        if not title or len(title) < 3:
            continue

        period_match = re.search(r"Q([1-4])[/\s]*(\d{4})", title)
        period = ""
        if period_match:
            period = f"Q{period_match.group(1)}/{period_match.group(2)}"

        if url.startswith("/"):
            url = "https://www.hnx.vn" + url

        reports.append(FinancialReport(
            period=period or title[:50],
            type="Báo cáo tài chính",
            pdf_url=url,
            source="HNX",
            source_url=url,
        ))

    if not reports:
        return None

    return ReportData(
        symbol=symbol,
        reports=reports,
        source="HNX",
        source_url=_HNX_URL.format(symbol=symbol),
        fetched_at=utcnow_iso(),
    )


def fetch_reports(symbol: str) -> ReportData | None:
    """Fetch financial reports from HNX."""
    url = _HNX_URL.format(symbol=symbol)
    html = fetch_html(url)
    if not html:
        return None
    return parse_reports(html, symbol)
