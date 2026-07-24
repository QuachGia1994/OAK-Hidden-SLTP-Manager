"""Data models for Local EOD Market Data Collector."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from typing import Any


@dataclass(frozen=True, slots=True)
class EODRecord:
    """Standardized EOD price record for Vietnam stock market."""

    date: str  # YYYY-MM-DD
    symbol: str
    exchange: str  # HOSE, HNX, UPCOM
    open: float
    high: float
    low: float
    close: float
    reference_price: float | None = None
    ceiling_price: float | None = None
    floor_price: float | None = None
    volume: float = 0.0
    value: float = 0.0
    source: str = "unknown"
    collected_at: str = ""
    foreign_buy_volume: float | None = None
    foreign_sell_volume: float | None = None
    foreign_buy_value: float | None = None
    foreign_sell_value: float | None = None
    adjusted_close: float | None = None

    def __post_init__(self) -> None:
        if not self.collected_at:
            object.__setattr__(self, "collected_at", datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RawFetchMetadata:
    """Metadata archive for raw fetch requests."""

    source_url: str
    downloaded_at: str
    status_code: int
    content_type: str
    sha256: str
    exchange: str
    trading_date: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
