"""Broker-calendar conversion derived from official MT5 UTC bar timestamps."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from threading import RLock
from typing import Any, Iterable


class BrokerClockError(ValueError):
    """Raised when a trustworthy broker UTC offset cannot be established."""


class BrokerClockUnavailableError(BrokerClockError):
    """Raised when MT5 cannot provide usable D1 history."""


class BrokerClock:
    """Resolve broker-local dates and times from MT5 D1 bar-open timestamps."""

    def __init__(self, mt5_module: Any, symbols: Iterable[str] = ("XAUUSD", "GBPUSD")):
        self._mt5 = mt5_module
        self._symbols = tuple(symbols)
        self._offsets: dict[date, int] = {}
        self._current_offsets: dict[date, int] = {}
        self._terminal_identity: tuple[Any, Any] | None = None
        self._lock = RLock()

    def utc_offset_for_date(self, broker_date: date) -> int:
        """Return the integer UTC offset used on one broker calendar date."""
        if not isinstance(broker_date, date):
            raise TypeError("broker_date must be a date")
        self._ensure_terminal_connection()
        with self._lock:
            cached = self._offsets.get(broker_date)
        if cached is not None:
            return cached
        self._load_offsets(broker_date - timedelta(days=7), broker_date + timedelta(days=7))
        with self._lock:
            offset = self._offsets.get(broker_date)
        if offset is None:
            raise BrokerClockError(f"no D1 broker offset for {broker_date.isoformat()}")
        return offset

    def current_utc_offset(self, now_utc: datetime | None = None) -> int:
        """Return today's broker offset, using the latest trustworthy D1 open."""
        self._ensure_terminal_connection()
        utc_now = self._as_utc(now_utc or datetime.now(timezone.utc))
        with self._lock:
            cached = self._current_offsets.get(utc_now.date())
        if cached is not None:
            return cached
        self._load_offsets(utc_now.date() - timedelta(days=10), utc_now.date() + timedelta(days=1))
        with self._lock:
            eligible = [(day, value) for day, value in self._offsets.items() if day <= utc_now.date() + timedelta(days=1)]
        if not eligible:
            raise BrokerClockError("no recent D1 broker offset is available")
        observed_date, offset = max(eligible, key=lambda item: item[0])
        if (utc_now.date() - observed_date).days > 4:
            raise BrokerClockError("latest D1 broker offset is stale")
        broker_today = (utc_now + timedelta(hours=offset)).date()
        with self._lock:
            self._store_offset(broker_today, offset)
            self._current_offsets[utc_now.date()] = offset
        return offset

    def now(self, now_utc: datetime | None = None) -> datetime:
        """Return the current naive broker-local datetime, or fail closed."""
        utc_now = self._as_utc(now_utc or datetime.now(timezone.utc))
        return (utc_now + timedelta(hours=self.current_utc_offset(utc_now))).replace(tzinfo=None)

    def utc_from_broker_datetime(self, broker_datetime: datetime) -> datetime:
        """Convert a naive broker-local datetime to an aware UTC datetime."""
        if broker_datetime.tzinfo is not None:
            raise BrokerClockError("broker datetime must be naive")
        offset = self.utc_offset_for_date(broker_datetime.date())
        return (broker_datetime - timedelta(hours=offset)).replace(tzinfo=timezone.utc)

    def broker_from_utc_datetime(self, utc_datetime: datetime) -> datetime:
        """Convert an aware UTC datetime to a naive broker-local datetime."""
        utc_value = self._as_utc(utc_datetime)
        offset = self.current_utc_offset(utc_value)
        candidate = (utc_value + timedelta(hours=offset)).replace(tzinfo=None)
        date_offset = self.utc_offset_for_date(candidate.date())
        return (utc_value + timedelta(hours=date_offset)).replace(tzinfo=None)

    def clear_cache(self) -> None:
        """Clear cached offsets, primarily after reconnecting an MT5 terminal."""
        with self._lock:
            self._offsets.clear()
            self._current_offsets.clear()

    def _ensure_terminal_connection(self) -> None:
        terminal_info = getattr(self._mt5, "terminal_info", None)
        try:
            if callable(terminal_info) and terminal_info() is None:
                raise BrokerClockUnavailableError("MT5 terminal is unavailable")
            account_reader = getattr(self._mt5, "account_info", None)
            account = account_reader() if callable(account_reader) else None
        except BrokerClockUnavailableError:
            raise
        except Exception as exc:
            raise BrokerClockUnavailableError("cannot read MT5 terminal state") from exc
        if not callable(account_reader):
            return
        if account is None:
            raise BrokerClockUnavailableError("MT5 account is unavailable")
        identity = (getattr(account, "server", None), getattr(account, "login", None))
        with self._lock:
            if self._terminal_identity is not None and identity != self._terminal_identity:
                self._offsets.clear()
                self._current_offsets.clear()
            self._terminal_identity = identity

    def _load_offsets(self, start_date: date, end_date: date) -> None:
        start_utc = datetime.combine(start_date - timedelta(days=1), time.min, timezone.utc)
        end_utc = datetime.combine(end_date + timedelta(days=1), time.max, timezone.utc)
        last_error: Exception | None = None
        for symbol in self._symbols:
            try:
                rates = self._copy_daily_rates(symbol, start_utc, end_utc)
                observations = self._observations(rates)
                if observations:
                    self._commit_observations(observations)
                    return
            except BrokerClockUnavailableError as exc:
                last_error = exc
        message = "cannot derive broker UTC offset from XAUUSD or GBPUSD D1 bars"
        raise BrokerClockUnavailableError(message) from last_error

    def _copy_daily_rates(self, symbol: str, start_utc: datetime, end_utc: datetime) -> Any:
        try:
            selected = self._mt5.symbol_select(symbol, True)
        except Exception as exc:
            raise BrokerClockUnavailableError(f"cannot select {symbol}") from exc
        if selected is False:
            raise BrokerClockUnavailableError(f"cannot select {symbol}")
        timeframe = getattr(self._mt5, "TIMEFRAME_D1", None)
        if timeframe is None or not hasattr(self._mt5, "copy_rates_range"):
            raise BrokerClockUnavailableError("MT5 D1 history API is unavailable")
        try:
            rates = self._mt5.copy_rates_range(symbol, timeframe, start_utc, end_utc)
        except Exception as exc:
            raise BrokerClockUnavailableError(f"cannot read {symbol} D1 bars") from exc
        if rates is None or len(rates) == 0:
            raise BrokerClockUnavailableError(f"no {symbol} D1 bars")
        return rates

    def _observations(self, rates: Any) -> list[tuple[date, int]]:
        observations: list[tuple[date, int]] = []
        for rate in rates:
            timestamp = self._rate_timestamp(rate)
            utc_open = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            offset = self._offset_from_daily_open(utc_open)
            broker_open = utc_open + timedelta(hours=offset)
            if broker_open.time().replace(tzinfo=None) != time.min:
                raise BrokerClockError("D1 bar does not map to broker midnight")
            observations.append((broker_open.date(), offset))
        observations.sort(key=lambda item: item[0])
        self._validate_observations(observations)
        return observations

    def _store_offset(self, broker_date: date, offset: int) -> None:
        existing = self._offsets.get(broker_date)
        if existing is not None and existing != offset:
            raise BrokerClockError(f"conflicting broker offsets for {broker_date.isoformat()}")
        neighbors = [value for day, value in self._offsets.items() if abs((day - broker_date).days) <= 7]
        if neighbors and min(abs(value - offset) for value in neighbors) > 1:
            raise BrokerClockError("broker offset changed by more than one hour")
        self._offsets[broker_date] = offset

    def _commit_observations(self, observations: list[tuple[date, int]]) -> None:
        with self._lock:
            previous = self._offsets
            self._offsets = dict(previous)
            try:
                for broker_date, offset in observations:
                    self._store_offset(broker_date, offset)
            except BrokerClockError:
                self._offsets = previous
                raise

    @staticmethod
    def _validate_observations(observations: list[tuple[date, int]]) -> None:
        for (previous_day, previous), (current_day, current) in zip(observations, observations[1:]):
            if current_day == previous_day and current != previous:
                raise BrokerClockError("conflicting D1 offsets for one broker date")
            if (current_day - previous_day).days <= 7 and abs(current - previous) > 1:
                raise BrokerClockError("broker offset changed by more than one hour")

    @staticmethod
    def _offset_from_daily_open(utc_open: datetime) -> int:
        if utc_open.minute or utc_open.second or utc_open.microsecond:
            raise BrokerClockError("D1 bar open is not aligned to a whole UTC hour")
        offset = -utc_open.hour
        if offset < -12:
            offset += 24
        if not -12 <= offset <= 14:
            raise BrokerClockError("derived broker UTC offset is invalid")
        return offset

    @staticmethod
    def _rate_timestamp(rate: Any) -> float:
        try:
            value = rate["time"]
        except (KeyError, IndexError, TypeError):
            value = getattr(rate, "time", None)
        if value is None:
            raise BrokerClockError("D1 bar has no UTC timestamp")
        return float(value)

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            raise BrokerClockError("UTC datetime must be timezone-aware")
        return value.astimezone(timezone.utc)
