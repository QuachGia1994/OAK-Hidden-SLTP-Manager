"""Market data adapter using Local EOD Data Collector (No API Key required)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
import math
import os
from typing import Any, Iterable, Sequence

from domain.stock_scanner import AfternoonPoint
from services.local_eod_data import LocalEODMarketDataProvider


class SSIMarketDataErrorCode(str, Enum):
    """Stable failure categories for market-data operations."""

    MISSING_CREDENTIALS = "missing_credentials"
    SDK_UNAVAILABLE = "sdk_unavailable"
    AUTHENTICATION_FAILED = "authentication_failed"
    DATA_REQUEST_FAILED = "data_request_failed"


class SSIConfigurationError(RuntimeError):
    """Configuration failure."""

    def __init__(self, code: SSIMarketDataErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class SSIMarketDataError(RuntimeError):
    """Market data request failure with a stable machine-readable code."""

    def __init__(self, code: SSIMarketDataErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class SSICredentials:
    """Credentials object (kept for backward compatibility; API keys are optional)."""

    client_id: str = "oak-stock-scanner"
    api_key: str = field(default="local-eod-key", repr=False)
    api_secret: str = field(default="local-eod-secret", repr=False)


def credentials_from_environment() -> SSICredentials:
    """Load credentials from environment or default to Local EOD mode (no API key required)."""
    client_id = os.environ.get("SSI_CLIENT_ID", "oak-stock-scanner").strip()
    api_key = os.environ.get("SSI_API_KEY", "local-eod-key").strip()
    api_secret = os.environ.get("SSI_API_SECRET", "local-eod-secret").strip()
    return SSICredentials(client_id, api_key, api_secret)


def aggregate_afternoon_vwap(candles: Iterable[object]) -> list[AfternoonPoint]:
    """Aggregate bars covering 13:05–13:09 into daily executable VWAPs."""
    daily: dict[date, list[tuple[float, float, float]]] = {}
    for candle in candles:
        timestamp = _candle_datetime(getattr(candle, "trading_date", None))
        if timestamp is None or not time(13, 5) <= timestamp.time() < time(13, 10):
            continue
        close = _positive_number(getattr(candle, "close_price", 0))
        volume = _positive_number(getattr(candle, "volume", 0))
        value = _positive_number(getattr(candle, "value", 0))
        if close == 0 or volume == 0:
            continue
        daily.setdefault(timestamp.date(), []).append((close, volume, value))
    return [_daily_vwap(trading_date, daily[trading_date]) for trading_date in sorted(daily)]


def _candle_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    patterns = (
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%Y/%m/%d",
        "%d/%m/%Y",
    )
    for pattern in patterns:
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _positive_number(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if (number > 0 and math.isfinite(number)) else 0.0


def _daily_vwap(trading_date: date, rows: Sequence[tuple[float, float, float]]) -> AfternoonPoint:
    total_volume = sum(row[1] for row in rows)
    total_value = sum(row[2] if row[2] > 0 else row[0] * row[1] for row in rows)
    return AfternoonPoint(trading_date, total_value / total_volume, total_value)


class SSIMarketDataProvider:
    """Market data provider backed by Local EOD SQLite database."""

    def __init__(
        self,
        credentials: SSICredentials | None = None,
        service_factory: Any = None,
    ) -> None:
        self._credentials = credentials or SSICredentials()
        self._service_factory = service_factory
        self._provider = LocalEODMarketDataProvider()

    def __enter__(self) -> SSIMarketDataProvider:
        self._provider.__enter__()
        return self

    def __exit__(self, *args: object) -> None:
        self._provider.__exit__(*args)

    def get_vn30_symbols(self) -> list[str]:
        """Return current VN30 constituents."""
        if self._service_factory:
            try:
                mock_service = self._service_factory(self._credentials, None)
                securities = mock_service.get_securities_info_by_index("VN30")
                symbols = {str(getattr(item, "symbol", "")).upper() for item in securities}
                return sorted(symbol for symbol in symbols if symbol)
            except Exception:
                pass
        return self._provider.get_vn30_symbols()

    def has_trading_session(self, trading_date: date) -> bool:
        """Return whether trading session exists for date."""
        if self._service_factory:
            try:
                mock_service = self._service_factory(self._credentials, None)
                summary = mock_service.get_index_summary("VNINDEX")
                ts = _candle_datetime(getattr(summary, "trading_date", None))
                return ts is not None and ts.date() == trading_date
            except Exception:
                pass
        return self._provider.has_trading_session(trading_date)

    def get_afternoon_points(self, symbol: str, from_date: date, to_date: date) -> list[AfternoonPoint]:
        """Return executable afternoon/EOD points for symbol."""
        if self._service_factory:
            try:
                mock_service = self._service_factory(self._credentials, None)
                candles: list[object] = []
                for page in range(1, 1001):
                    page_data = mock_service.get_ohlc_5minute_historical(
                        symbol=symbol,
                        from_date=from_date.strftime("%Y/%m/%d"),
                        to_date=to_date.strftime("%Y/%m/%d"),
                        page=page,
                        size=1000,
                    )
                    if page_data:
                        candles.extend(page_data)
                    if not page_data or len(page_data) < 1000:
                        break
                return aggregate_afternoon_vwap(candles)
            except Exception:
                pass
        return self._provider.get_afternoon_points(symbol, from_date, to_date)
