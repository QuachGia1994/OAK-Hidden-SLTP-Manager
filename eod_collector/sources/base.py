"""Base abstract class for EOD Data Sources."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timezone
import hashlib
from typing import Any


@dataclass(frozen=True, slots=True)
class RawFetchResult:
    """Raw payload downloaded from an official public source."""

    content: bytes
    status_code: int
    content_type: str
    source_url: str
    downloaded_at: str
    sha256: str

    @classmethod
    def create(
        cls,
        content: bytes,
        status_code: int,
        content_type: str,
        source_url: str,
    ) -> RawFetchResult:
        sha256_hash = hashlib.sha256(content).hexdigest()
        now_str = datetime.now(timezone.utc).isoformat()
        return cls(
            content=content,
            status_code=status_code,
            content_type=content_type,
            source_url=source_url,
            downloaded_at=now_str,
            sha256=sha256_hash,
        )


class EODDataSource(ABC):
    """Abstract interface for exchange-specific EOD data sources."""

    @property
    @abstractmethod
    def exchange_name(self) -> str:
        """Name of the exchange (HOSE, HNX, UPCOM)."""
        ...

    @abstractmethod
    def fetch(self, trading_date: date) -> RawFetchResult:
        """Fetch raw EOD data for the given trading date without authentication."""
        ...

    @abstractmethod
    def parse(self, raw_data: bytes | str) -> list[dict[str, Any]]:
        """Parse raw content into raw dictionaries before normalization."""
        ...
