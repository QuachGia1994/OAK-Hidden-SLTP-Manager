"""HNX parser — company profile from Hanoi Stock Exchange."""
from __future__ import annotations

import logging
import re
from typing import Any

from stock_data_crawler.models import StockProfile, utcnow_iso
from stock_data_crawler.http_client import fetch_html

logger = logging.getLogger("stock_data_crawler")

_HNX_URL = "https://www.hnx.vn/co-phieu/{symbol}"


def _extract_text(html: str, pattern: str) -> str:
    m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else ""


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
