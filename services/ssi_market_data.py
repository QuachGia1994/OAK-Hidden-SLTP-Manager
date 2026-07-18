"""Read-only SSI FastConnect market-data adapter for the stock scanner."""
from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
import os
from typing import Callable, Iterable, Protocol, Sequence

from domain.stock_scanner import AfternoonPoint


class SSIMarketDataErrorCode(str, Enum):
    """Stable failure categories for SSI market-data operations."""

    MISSING_CREDENTIALS = "missing_credentials"
    SDK_UNAVAILABLE = "sdk_unavailable"
    AUTHENTICATION_FAILED = "authentication_failed"
    DATA_REQUEST_FAILED = "data_request_failed"


class SSIConfigurationError(RuntimeError):
    """SSI configuration failure that never embeds credential values."""

    def __init__(self, code: SSIMarketDataErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


class SSIMarketDataError(RuntimeError):
    """SSI request failure with a stable machine-readable code."""

    def __init__(self, code: SSIMarketDataErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class SSICredentials:
    """Read-only FastConnect credentials with a redacted secret repr."""

    client_id: str
    api_key: str = field(repr=False)
    api_secret: str = field(repr=False)


class MarketDataService(Protocol):
    """Subset of the official SSI SDK used by the scanner."""

    def get_securities_info_by_index(self, index: str) -> Sequence[object]: ...

    def get_index_summary(self, index: str) -> object | None: ...

    def get_ohlc_5minute_historical(
        self, symbol: str, from_date: str, to_date: str, page: int, size: int
    ) -> Sequence[object]: ...


def credentials_from_environment() -> SSICredentials:
    """Load read-only SSI credentials from environment variables."""
    client_id = os.environ.get("SSI_CLIENT_ID", "oak-stock-scanner").strip()
    api_key = os.environ.get("SSI_API_KEY", "").strip()
    api_secret = os.environ.get("SSI_API_SECRET", "").strip()
    if not api_key or not api_secret:
        raise SSIConfigurationError(
            SSIMarketDataErrorCode.MISSING_CREDENTIALS,
            "SSI_API_KEY and SSI_API_SECRET are required",
        )
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


class SSIMarketDataProvider:
    """Context-managed, market-data-only wrapper around official ``ssi-sdk``."""

    def __init__(
        self,
        credentials: SSICredentials,
        service_factory: Callable[[SSICredentials, ExitStack], MarketDataService] | None = None,
    ) -> None:
        self._credentials = credentials
        self._service_factory = service_factory or _open_official_service
        self._stack: ExitStack | None = None
        self._service: MarketDataService | None = None

    def __enter__(self) -> SSIMarketDataProvider:
        self._stack = ExitStack()
        try:
            self._service = self._service_factory(self._credentials, self._stack)
        except SSIConfigurationError:
            self._stack.close()
            raise
        except Exception as error:
            self._stack.close()
            raise SSIMarketDataError(
                SSIMarketDataErrorCode.AUTHENTICATION_FAILED,
                f"SSI market-data authentication failed: {type(error).__name__}",
            ) from error
        return self

    def __exit__(self, *_: object) -> None:
        if self._stack is not None:
            self._stack.close()
        self._stack, self._service = None, None

    def get_vn30_symbols(self) -> list[str]:
        """Return the current VN30 constituents from SSI."""
        service = self._require_service()
        try:
            securities = service.get_securities_info_by_index("VN30")
        except Exception as error:
            raise self._request_error("VN30 constituents", error) from error
        symbols = {str(getattr(item, "symbol", "")).upper() for item in securities}
        return sorted(symbol for symbol in symbols if symbol)

    def has_trading_session(self, trading_date: date) -> bool:
        """Return whether SSI reports an active VNINDEX session for the date."""
        service = self._require_service()
        try:
            summary = service.get_index_summary("VNINDEX")
        except Exception as error:
            raise self._request_error("VNINDEX session", error) from error
        timestamp = _candle_datetime(getattr(summary, "trading_date", None))
        return timestamp is not None and timestamp.date() == trading_date

    def get_afternoon_points(self, symbol: str, from_date: date, to_date: date) -> list[AfternoonPoint]:
        """Return historical 13:05–13:09 VWAP points for one symbol."""
        service = self._require_service()
        candles: list[object] = []
        for page in range(1, 1001):
            page_data = self._minute_page(service, symbol, from_date, to_date, page)
            candles.extend(page_data)
            if len(page_data) < 1000:
                break
        return aggregate_afternoon_vwap(candles)

    def _minute_page(
        self, service: MarketDataService, symbol: str, from_date: date, to_date: date, page: int
    ) -> Sequence[object]:
        try:
            return service.get_ohlc_5minute_historical(
                symbol=symbol,
                from_date=from_date.strftime("%Y/%m/%d"),
                to_date=to_date.strftime("%Y/%m/%d"),
                page=page,
                size=1000,
            )
        except Exception as error:
            raise self._request_error(f"OHLC for {symbol}", error) from error

    def _require_service(self) -> MarketDataService:
        if self._service is None:
            raise SSIMarketDataError(SSIMarketDataErrorCode.DATA_REQUEST_FAILED, "SSI provider is not open")
        return self._service

    @staticmethod
    def _request_error(operation: str, error: Exception) -> SSIMarketDataError:
        return SSIMarketDataError(
            SSIMarketDataErrorCode.DATA_REQUEST_FAILED,
            f"SSI {operation} failed: {type(error).__name__}",
        )


def _open_official_service(credentials: SSICredentials, stack: ExitStack) -> MarketDataService:
    try:
        from ssi_sdk import Auth, Config, Data
    except ImportError as error:
        raise SSIConfigurationError(
            SSIMarketDataErrorCode.SDK_UNAVAILABLE,
            "ssi-sdk is not installed",
        ) from error
    config = Config(client_id=credentials.client_id, api_key=credentials.api_key, api_secret=credentials.api_secret)
    auth = stack.enter_context(Auth(config))
    auth.authenticate()
    data = stack.enter_context(Data(auth))
    return data.market_data


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
    return number if number > 0 else 0.0


def _daily_vwap(trading_date: date, rows: Sequence[tuple[float, float, float]]) -> AfternoonPoint:
    total_volume = sum(row[1] for row in rows)
    total_value = sum(row[2] if row[2] > 0 else row[0] * row[1] for row in rows)
    return AfternoonPoint(trading_date, total_value / total_volume, total_value)
