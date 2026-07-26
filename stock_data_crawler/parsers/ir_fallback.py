"""IR website fallback — scrape company Investor Relations pages for PDF reports."""
from __future__ import annotations

import logging
import re
from typing import Any

from stock_data_crawler.models import ReportData, FinancialReport, utcnow_iso
from stock_data_crawler.http_client import fetch_html, escape_html_text

logger = logging.getLogger("stock_data_crawler")

# Known IR website URL patterns for major Vietnamese companies
_IR_URL_MAP: dict[str, str] = {
    "HPG": "https://www.hoaphat.com.vn/quan-he-co-dong/bao-cao-tai-chinh",
    "VNM": "https://www.vinamilk.com.vn/vi/quan-he-co-dong/bao-cao-tai-chinh",
    "FPT": "https://www.fpt.com.vn/vi/quan-he-co-dong/bao-cao-tai-chinh",
    "VCB": "https://www.vietcombank.com.vn/vi/nha-dau-tu/bao-cao-tai-chinh",
    "TCB": "https://www.techcombank.com.vn/nha-dau-tu/bao-cao-tai-chinh",
    "MWG": "https://www.thegioididong.com/quan-he-co-dong/bao-cao-tai-chinh",
    "MSN": "https://www.msn.com.vn/quan-he-co-dong/bao-cao-tai-chinh",
    "SSI": "https://www.ssi.com.vn/quan-he-co-dong/bao-cao-tai-chinh",
    "BID": "https://www.bidv.com.vn/nha-dau-tu/bao-cao-tai-chinh",
    "CTG": "https://www.vietinbank.vn/vi/nha-dau-tu/bao-cao-tai-chinh",
    "TMS": "https://www.transimex.com.vn/quan-he-co-dong/bao-cao-tai-chinh",
    "VIC": "https://www.vingroup.vn/quan-he-co-dong/bao-cao-tai-chinh",
    "GAS": "https://www.pvgas.com.vn/quan-he-co-dong/bao-cao-tai-chinh",
    "PLX": "https://www.petrolimex.com.vn/quan-he-co-dong/bao-cao-tai-chinh",
    "SAB": "https://www.sabeco.com.vn/quan-he-co-dong/bao-cao-tai-chinh",
    "BVH": "https://www.baoviet.com.vn/Investor/Pages/bao-cao-tai-chinh.aspx",
    "VJC": "https://www.vietjetair.com/vi/nha-dau-tu/bao-cao-tai-chinh",
    "VRE": "https://www.vincomretail.com/quan-he-co-dong/bao-cao-tai-chinh",
    "PNJ": "https://www.pnj.com.vn/quan-he-co-dong/bao-cao-tai-chinh",
    "HDB": "https://www.hdbank.com.vn/vi/quan-he-co-dong/bao-cao-tai-chinh",
}


def parse_reports(html: str, symbol: str, source_url: str) -> ReportData | None:
    """Parse IR page HTML to extract PDF report links."""
    reports: list[FinancialReport] = []

    # Look for PDF links
    pdf_links = re.findall(
        r'<a[^>]*href="([^"]*\.pdf[^"]*)"[^>]*>([^<]+)</a>',
        html,
        re.IGNORECASE,
    )

    for url, title in pdf_links[:20]:
        title = escape_html_text(title.strip())
        if not title or len(title) < 3:
            continue

        period_match = re.search(r"Q([1-4])[/\s]*(\d{4})", title)
        period = ""
        if period_match:
            period = f"Q{period_match.group(1)}/{period_match.group(2)}"

        # Normalize URL
        if url.startswith("/"):
            from urllib.parse import urljoin
            url = urljoin(source_url, url)

        reports.append(FinancialReport(
            period=period or title[:50],
            type="Báo cáo tài chính",
            pdf_url=url,
            source="IR",
            source_url=url,
        ))

    if not reports:
        return None

    return ReportData(
        symbol=symbol,
        reports=reports,
        source="IR",
        source_url=source_url,
        fetched_at=utcnow_iso(),
    )


def fetch_reports(symbol: str) -> ReportData | None:
    """Fetch financial reports from company IR website."""
    url = _IR_URL_MAP.get(symbol.upper())
    if not url:
        return None

    html = fetch_html(url)
    if not html:
        return None
    return parse_reports(html, symbol, url)