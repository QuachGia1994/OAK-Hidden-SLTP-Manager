"""SSC parser — financial reports from State Securities Commission disclosure portal."""
from __future__ import annotations

import logging
import re
from typing import Any

from stock_data_crawler.models import ReportData, FinancialReport, utcnow_iso
from stock_data_crawler.http_client import fetch_html, escape_html_text

logger = logging.getLogger("stock_data_crawler")

# CafeF SSC proxy (SSC itself requires auth, CafeF mirrors the data)
_SSC_URL = "https://s.cafef.vn/hose/{symbol}-cong-ty-co-phuong-thuoc-san.chn"


def parse_reports(html: str, symbol: str) -> ReportData | None:
    """Parse HTML to extract financial report listings."""
    reports: list[FinancialReport] = []

    # Look for PDF links with report titles
    pdf_links = re.findall(
        r'<a[^>]*href="([^"]*\.pdf[^"]*)"[^>]*>([^<]+)</a>',
        html,
        re.IGNORECASE,
    )

    for url, title in pdf_links[:10]:
        title = escape_html_text(title.strip())
        if not title or len(title) < 5:
            continue

        # Extract period from title (Q1/2026, Q2/2025, etc.)
        period_match = re.search(r"Q([1-4])[/\s]*(\d{4})", title)
        period = ""
        if period_match:
            period = f"Q{period_match.group(1)}/{period_match.group(2)}"

        # Normalize URL
        if url.startswith("/"):
            url = "https://s.cafef.vn" + url

        reports.append(FinancialReport(
            period=period or title[:50],
            type="Báo cáo tài chính",
            pdf_url=url,
            source="SSC/CafeF",
            source_url=url,
        ))

    # Also look for report table rows
    rows = re.findall(
        r"<tr[^>]*>.*?</tr>",
        html,
        re.DOTALL | re.IGNORECASE,
    )
    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
        if len(cells) < 2:
            continue

        # Check for period pattern in cells
        for cell in cells:
            period_match = re.search(r"Q([1-4])[/\s]*(\d{4})", cell)
            if period_match:
                period = f"Q{period_match.group(1)}/{period_match.group(2)}"
                # Look for PDF link in same row
                link_match = re.search(r'href="([^"]*\.pdf[^"]*)"', row)
                pdf_url = ""
                if link_match:
                    pdf_url = link_match.group(1)
                    if pdf_url.startswith("/"):
                        pdf_url = "https://s.cafef.vn" + pdf_url

                # Avoid duplicates
                if not any(r.period == period for r in reports):
                    reports.append(FinancialReport(
                        period=period,
                        type="Báo cáo tài chính",
                        pdf_url=pdf_url,
                        source="SSC/CafeF",
                        source_url=pdf_url or _SSC_URL.format(symbol=symbol),
                    ))
                break

    if not reports:
        return None

    return ReportData(
        symbol=symbol,
        reports=reports,
        source="SSC/CafeF",
        source_url=_SSC_URL.format(symbol=symbol),
        fetched_at=utcnow_iso(),
    )


def fetch_reports(symbol: str) -> ReportData | None:
    """Fetch financial reports from SSC/CafeF."""
    url = _SSC_URL.format(symbol=symbol)
    html = fetch_html(url)
    if not html:
        return None
    return parse_reports(html, symbol)
