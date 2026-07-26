"""Data models for stock data crawled from public sources."""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class StockProfile:
    symbol: str
    name: str
    exchange: str
    industry: str = ""
    market_cap: float = 0
    source: str = ""
    source_url: str = ""
    fetched_at: str = ""
    stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v or k in ("symbol", "name", "exchange")}


@dataclass
class FinancialReport:
    period: str
    type: str
    published_at: str = ""
    pdf_url: str = ""
    source: str = ""
    source_url: str = ""


@dataclass
class ReportData:
    symbol: str
    reports: list[FinancialReport] = field(default_factory=list)
    source: str = ""
    source_url: str = ""
    fetched_at: str = ""
    stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "reports": [asdict(r) for r in self.reports],
            "source": self.source,
            "sourceUrl": self.source_url,
            "fetchedAt": self.fetched_at,
            "stale": self.stale,
        }


@dataclass
class DividendEntry:
    ex_date: str
    pay_date: str = ""
    cash_amount: float = 0
    stock_ratio: float = 0
    source: str = ""
    source_url: str = ""


@dataclass
class DividendData:
    symbol: str
    dividends: list[DividendEntry] = field(default_factory=list)
    source: str = ""
    source_url: str = ""
    fetched_at: str = ""
    stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "dividends": [asdict(d) for d in self.dividends],
            "source": self.source,
            "sourceUrl": self.source_url,
            "fetchedAt": self.fetched_at,
            "stale": self.stale,
        }


@dataclass
class ForeignTrade:
    date: str
    buyVol: float = 0
    sellVol: float = 0


@dataclass
class TopShareholder:
    name: str = ""
    ratio: float = 0
    type: str = ""  # "TN", "TC", "BLĐ"


@dataclass
class ForeignData:
    symbol: str
    foreign_ratio: float = 0
    institutional_ratio: float = 0
    management_ratio: float = 0
    top_shareholders: list[TopShareholder] = field(default_factory=list)
    recent_trades: list[ForeignTrade] = field(default_factory=list)
    source: str = ""
    source_url: str = ""
    fetched_at: str = ""
    stale: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "foreignRatio": self.foreign_ratio,
            "institutionalRatio": self.institutional_ratio,
            "managementRatio": self.management_ratio,
            "topShareholders": [asdict(sh) for sh in self.top_shareholders],
            "recentTrades": [asdict(t) for t in self.recent_trades],
            "source": self.source,
            "sourceUrl": self.source_url,
            "fetchedAt": self.fetched_at,
            "stale": self.stale,
        }


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
