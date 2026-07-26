"""VSDC parser — dividend history from Vietnam Securities Depository Center."""
from __future__ import annotations

import logging
import re
from typing import Any

from stock_data_crawler.models import DividendData, DividendEntry, utcnow_iso
from stock_data_crawler.http_client import fetch_html

logger = logging.getLogger("stock_data_crawler")

_VSDC_URL = "https://www.vsd.vn/du-lieu-co-phieu-{symbol}"


def _parse_number(text: str) -> float:
    """Parse Vietnamese number format (1.500 → 1500)."""
    text = text.strip().replace(".", "").replace(",", ".")
    try:
        return float(text)
    except (ValueError, TypeError):
        return 0


def parse_dividends(html: str, symbol: str) -> DividendData | None:
    """Parse VSDC HTML to extract dividend history."""
    dividends: list[DividendEntry] = []

    # Look for dividend table rows
    # Pattern: date | ex_date | cash_amount | stock_ratio
    rows = re.findall(
        r"<tr[^>]*>.*?</tr>",
        html,
        re.DOTALL | re.IGNORECASE,
    )

    for row in rows:
        cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.DOTALL | re.IGNORECASE)
        if len(cells) < 3:
            continue

        # Extract dates
        dates = re.findall(r"(\d{2}/\d{2}/\d{4})", " ".join(cells))
        ex_date = dates[0] if dates else ""
        pay_date = dates[1] if len(dates) > 1 else ""

        # Extract cash/stock amounts
        amounts = []
        for cell in cells[2:5]:
            nums = re.findall(r"[\d.]+", cell)
            if nums:
                amounts.append(_parse_number(nums[0]))

        cash = amounts[0] if amounts else 0
        stock = amounts[1] if len(amounts) > 1 else 0

        if ex_date and (cash > 0 or stock > 0):
            dividends.append(DividendEntry(
                ex_date=ex_date,
                pay_date=pay_date,
                cash_amount=cash,
                stock_ratio=stock,
                source="VSDC",
                source_url=_VSDC_URL.format(symbol=symbol),
            ))

    if not dividends:
        return None

    return DividendData(
        symbol=symbol,
        dividends=dividends[:10],
        fetched_at=utcnow_iso(),
    )


def fetch_dividends(symbol: str) -> DividendData | None:
    """Fetch dividend history from VSDC."""
    url = _VSDC_URL.format(symbol=symbol)
    html = fetch_html(url)
    if not html:
        return None
    return parse_dividends(html, symbol)
