"""Fail-closed Broker clock calibrated against the connected MT5 terminal."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time as time_module
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Iterable


class BrokerClockError(ValueError):
    """Raised when a trustworthy Broker UTC offset cannot be established."""


class BrokerClockUnavailableError(BrokerClockError):
    """Raised when MT5 cannot provide usable clock observations."""


class BrokerClock:
    """Resolve Broker wall time and the terminal's timestamp encoding."""

    _MAX_TICK_AGE_SECONDS = 300
    _MAX_WALL_EXTRAPOLATION_DAYS = 45
    _CALIBRATION_SAMPLE_SECONDS = 2.0
    _VALID_MODES = frozenset(("utc", "broker_wall"))
    _VERIFIED_SOURCES = frozenset(("live", "d1-utc", "restart-verified"))

    def __init__(
        self,
        mt5_module: Any,
        symbols: Iterable[str] = ("XAUUSD", "GBPUSD", "BTCUSD"),
        cache_path: str | os.PathLike[str] | None = None,
    ):
        self._mt5 = mt5_module
        self._symbols = tuple(dict.fromkeys(symbols))
        self._daily_symbols = tuple(
            symbol for symbol in self._symbols if not symbol.upper().startswith("BTC")
        ) or self._symbols
        self._cache_path = Path(cache_path) if cache_path else None
        self._offsets: dict[date, int] = {}
        self._offset_sources: dict[date, str] = {}
        self._verified_offset_dates: set[date] = set()
        self._current_offsets: dict[date, int] = {}
        self._timestamp_mode: str | None = None
        self._terminal_identity: tuple[Any, Any] | None = None
        self._identity_key: str | None = None
        self._lock = RLock()

    @property
    def timestamp_mode(self) -> str | None:
        """Return ``utc`` or ``broker_wall`` after successful calibration."""
        with self._lock:
            return self._timestamp_mode

    def current_utc_offset(self, now_utc: datetime | None = None) -> int:
        """Return the current Broker UTC offset after validating terminal state."""
        self._ensure_terminal_connection()
        utc_now = self._as_utc(now_utc or datetime.now(timezone.utc))
        with self._lock:
            cached = self._current_offsets.get(utc_now.date())
        if cached is not None:
            return cached

        source = "live"
        try:
            mode, observed_offset = self._calibrate_timestamp_mode(utc_now)
            self._set_timestamp_mode(mode)
            offset = self._offset_for_live_observation(utc_now, observed_offset)
        except BrokerClockUnavailableError:
            offset = self._current_offset_from_cache(utc_now)
            source = "cache-fallback"

        broker_date = (utc_now + timedelta(hours=offset)).date()
        with self._lock:
            self._store_offset(broker_date, offset, source)
            self._current_offsets[utc_now.date()] = offset
        self._persist_cache()
        return offset

    def utc_offset_for_date(self, broker_date: date) -> int:
        """Return the UTC offset used on one Broker calendar date."""
        if not isinstance(broker_date, date):
            raise TypeError("broker_date must be a date")
        self._ensure_terminal_connection()
        with self._lock:
            cached = self._offsets.get(broker_date)
            mode = self._timestamp_mode
        if cached is not None:
            return cached
        if mode is None:
            self.current_utc_offset()
            with self._lock:
                mode = self._timestamp_mode
        if mode == "utc":
            self._load_utc_offsets(broker_date - timedelta(days=7), broker_date + timedelta(days=7))
        elif mode == "broker_wall":
            self._extrapolate_wall_offset(broker_date)
        with self._lock:
            offset = self._offsets.get(broker_date)
        if offset is None:
            raise BrokerClockError(f"no verified Broker offset for {broker_date.isoformat()}")
        return offset

    def now(self, now_utc: datetime | None = None) -> datetime:
        """Return the current naive Broker wall-clock datetime."""
        utc_now = self._as_utc(now_utc or datetime.now(timezone.utc))
        offset = self.current_utc_offset(utc_now)
        return (utc_now + timedelta(hours=offset)).replace(tzinfo=None)

    def utc_from_broker_datetime(self, broker_datetime: datetime) -> datetime:
        """Convert a naive Broker datetime into an absolute UTC datetime."""
        self._require_naive_broker_datetime(broker_datetime)
        offset = self.utc_offset_for_date(broker_datetime.date())
        return (broker_datetime - timedelta(hours=offset)).replace(tzinfo=timezone.utc)

    def mt5_timestamp_from_broker_datetime(self, broker_datetime: datetime) -> int:
        """Encode Broker wall time exactly as the connected MT5 terminal does."""
        self._require_naive_broker_datetime(broker_datetime)
        self.utc_offset_for_date(broker_datetime.date())
        with self._lock:
            mode = self._timestamp_mode
        if mode == "broker_wall":
            return int(broker_datetime.replace(tzinfo=timezone.utc).timestamp())
        if mode == "utc":
            return int(self.utc_from_broker_datetime(broker_datetime).timestamp())
        raise BrokerClockError("MT5 timestamp mode is not calibrated")

    def broker_from_utc_datetime(self, utc_datetime: datetime) -> datetime:
        """Convert an aware UTC datetime into a naive Broker datetime."""
        utc_value = self._as_utc(utc_datetime)
        offset = self.current_utc_offset(utc_value)
        candidate = (utc_value + timedelta(hours=offset)).replace(tzinfo=None)
        date_offset = self.utc_offset_for_date(candidate.date())
        return (utc_value + timedelta(hours=date_offset)).replace(tzinfo=None)

    def clear_cache(self) -> None:
        """Clear volatile calibration while retaining the restart cache file."""
        with self._lock:
            self._offsets.clear()
            self._offset_sources.clear()
            self._verified_offset_dates.clear()
            self._current_offsets.clear()
            self._timestamp_mode = None
            self._terminal_identity = None
            self._identity_key = None

    def _offset_for_live_observation(self, utc_now: datetime, observed_offset: int) -> int:
        with self._lock:
            mode = self._timestamp_mode
        if mode == "broker_wall":
            return observed_offset
        if mode != "utc":
            raise BrokerClockError("MT5 timestamp mode is not calibrated")
        return self._current_utc_offset_from_d1(utc_now)

    def _calibrate_timestamp_mode(self, utc_now: datetime) -> tuple[str, int]:
        first_sample = self._read_tick_timestamps()
        if not first_sample:
            raise BrokerClockUnavailableError("no MT5 calibration tick is available")
        time_module.sleep(self._CALIBRATION_SAMPLE_SECONDS)
        second_utc = utc_now + timedelta(seconds=self._CALIBRATION_SAMPLE_SECONDS)
        second_sample = self._read_tick_timestamps()
        candidates = []
        for symbol, latest in second_sample.items():
            previous = first_sample.get(symbol)
            if previous is None or latest <= previous:
                continue
            candidates.append(self._timestamp_candidate(latest, second_utc))
        if not candidates:
            raise BrokerClockUnavailableError("MT5 ticks did not advance during calibration")
        offsets = {offset for offset, _residual in candidates}
        if len(offsets) != 1:
            raise BrokerClockUnavailableError("MT5 calibration symbols disagree on Broker offset")
        offset = offsets.pop()
        return ("utc" if offset == 0 else "broker_wall", offset)

    def _timestamp_candidate(self, timestamp: float, utc_now: datetime) -> tuple[int, float]:
        delta_seconds = timestamp - utc_now.timestamp()
        offset = round(delta_seconds / 3600)
        residual = delta_seconds - offset * 3600
        if not -12 <= offset <= 14:
            raise BrokerClockUnavailableError("latest MT5 tick is stale")
        if not -self._MAX_TICK_AGE_SECONDS <= residual <= 30:
            raise BrokerClockUnavailableError("latest MT5 tick is not fresh")
        return offset, residual

    def _read_tick_timestamps(self) -> dict[str, float]:
        timestamps: dict[str, float] = {}
        for symbol in self._symbols:
            try:
                if self._mt5.symbol_select(symbol, True) is False:
                    continue
                tick = self._mt5.symbol_info_tick(symbol)
                timestamp = self._tick_timestamp(tick)
                if timestamp is not None:
                    timestamps[symbol] = timestamp
            except Exception:
                continue
        return timestamps

    @staticmethod
    def _tick_timestamp(tick: Any) -> float | None:
        if tick is None:
            return None
        milliseconds = getattr(tick, "time_msc", None)
        if milliseconds:
            return float(milliseconds) / 1000
        seconds = getattr(tick, "time", None)
        return float(seconds) if seconds else None

    def _current_utc_offset_from_d1(self, utc_now: datetime) -> int:
        self._load_utc_offsets(utc_now.date() - timedelta(days=10), utc_now.date() + timedelta(days=1))
        with self._lock:
            eligible = [(day, value) for day, value in self._offsets.items() if day <= utc_now.date() + timedelta(days=1)]
        if not eligible:
            raise BrokerClockError("no recent D1 Broker offset is available")
        observed_date, offset = max(eligible, key=lambda item: item[0])
        if (utc_now.date() - observed_date).days > 4:
            raise BrokerClockError("latest D1 Broker offset is stale")
        return offset

    def _current_offset_from_cache(self, utc_now: datetime) -> int:
        with self._lock:
            candidates = [
                (broker_date, self._offsets[broker_date])
                for broker_date in self._verified_offset_dates
                if broker_date in self._offsets
            ]
        eligible: list[tuple[int, int]] = []
        for observed_date, offset in candidates:
            broker_today = (utc_now + timedelta(hours=offset)).date()
            distance = abs((broker_today - observed_date).days)
            same_day = distance == 0
            safely_extrapolated = (
                distance <= self._MAX_WALL_EXTRAPOLATION_DAYS
                and self._same_stable_period(observed_date, broker_today)
            )
            if same_day or safely_extrapolated:
                eligible.append((distance, offset))
        if not eligible:
            raise BrokerClockUnavailableError("no fresh tick or safe cached Broker offset")
        return min(eligible, key=lambda item: item[0])[1]

    def _extrapolate_wall_offset(self, broker_date: date) -> None:
        with self._lock:
            anchors = [
                (anchor_date, self._offsets[anchor_date])
                for anchor_date in self._verified_offset_dates
                if anchor_date in self._offsets
            ]
        eligible = [
            (abs((broker_date - anchor_date).days), offset)
            for anchor_date, offset in anchors
            if abs((broker_date - anchor_date).days) <= self._MAX_WALL_EXTRAPOLATION_DAYS
            and self._same_stable_period(anchor_date, broker_date)
        ]
        if not eligible:
            raise BrokerClockError(f"cannot safely infer DST offset for {broker_date.isoformat()}")
        _, offset = min(eligible, key=lambda item: item[0])
        with self._lock:
            self._store_offset(broker_date, offset, "stable-window")
        self._persist_cache()

    @staticmethod
    def _same_stable_period(first: date, second: date) -> bool:
        first_period = BrokerClock._stable_period(first)
        return first_period is not None and first_period == BrokerClock._stable_period(second)

    @staticmethod
    def _stable_period(value: date) -> tuple[str, int] | None:
        month_day = (value.month, value.day)
        # US DST transitions: spring forward ~mid-March, fall back ~early November
        # Broker timezone follows US DST schedule
        if (4, 1) <= month_day <= (9, 30):
            return ("summer", value.year)
        if month_day >= (11, 1) or month_day <= (2, 29):
            return ("winter", value.year)
        # March 1–31 and October 1–31 are transition months — classify by which DST regime is closer
        if month_day[0] == 3:
            # March: second Sunday onward is summer (US spring forward)
            second_sunday = BrokerClock._nth_sunday_of_month(value.year, 3, 2)
            if value.day >= second_sunday:
                return ("summer", value.year)
            return ("winter", value.year)
        if month_day[0] == 10:
            # October: after first Sunday is winter (US fall back is first Sunday of November)
            # October is still summer until November transition
            return ("summer", value.year)
        return None

    @staticmethod
    def _nth_sunday_of_month(year: int, month: int, n: int) -> int:
        """Return the day number of the Nth Sunday in a given month (1-indexed)."""
        first_day = date(year, month, 1)
        first_sunday = 1 + (6 - first_day.weekday()) % 7
        return first_sunday + (n - 1) * 7

    def _load_utc_offsets(self, start_date: date, end_date: date) -> None:
        start_utc = datetime.combine(start_date - timedelta(days=1), time.min, timezone.utc)
        end_utc = datetime.combine(end_date + timedelta(days=1), time.max, timezone.utc)
        last_error: Exception | None = None
        for symbol in self._daily_symbols:
            try:
                observations = self._utc_observations(self._copy_daily_rates(symbol, start_utc, end_utc))
                if observations:
                    self._commit_observations(observations)
                    self._persist_cache()
                    return
            except BrokerClockUnavailableError as error:
                last_error = error
        raise BrokerClockUnavailableError("cannot derive Broker offset from UTC D1 bars") from last_error

    def _copy_daily_rates(self, symbol: str, start_utc: datetime, end_utc: datetime) -> Any:
        if self._mt5.symbol_select(symbol, True) is False:
            raise BrokerClockUnavailableError(f"cannot select {symbol}")
        timeframe = getattr(self._mt5, "TIMEFRAME_D1", None)
        if timeframe is None or not hasattr(self._mt5, "copy_rates_range"):
            raise BrokerClockUnavailableError("MT5 D1 history API is unavailable")
        try:
            rates = self._mt5.copy_rates_range(symbol, timeframe, start_utc, end_utc)
        except Exception as error:
            raise BrokerClockUnavailableError(f"cannot read {symbol} D1 bars") from error
        if rates is None or len(rates) == 0:
            raise BrokerClockUnavailableError(f"no {symbol} D1 bars")
        return rates

    def _utc_observations(self, rates: Any) -> list[tuple[date, int]]:
        observations: list[tuple[date, int]] = []
        for rate in rates:
            utc_open = datetime.fromtimestamp(self._rate_timestamp(rate), tz=timezone.utc)
            offset = self._offset_from_daily_open(utc_open)
            broker_open = utc_open + timedelta(hours=offset)
            if broker_open.time().replace(tzinfo=None) != time.min:
                raise BrokerClockError("D1 bar does not map to Broker midnight")
            observations.append((broker_open.date(), offset))
        observations.sort(key=lambda item: item[0])
        self._validate_observations(observations)
        return observations

    def _commit_observations(self, observations: list[tuple[date, int]]) -> None:
        with self._lock:
            previous_offsets = dict(self._offsets)
            previous_sources = dict(self._offset_sources)
            previous_verified_dates = set(self._verified_offset_dates)
            try:
                for broker_date, offset in observations:
                    self._store_offset(broker_date, offset, "d1-utc")
            except BrokerClockError:
                self._offsets = previous_offsets
                self._offset_sources = previous_sources
                self._verified_offset_dates = previous_verified_dates
                raise

    def _store_offset(self, broker_date: date, offset: int, source: str) -> None:
        if not -12 <= offset <= 14:
            raise BrokerClockError("Broker UTC offset is invalid")
        existing = self._offsets.get(broker_date)
        if existing is not None and existing != offset:
            raise BrokerClockError(f"conflicting Broker offsets for {broker_date.isoformat()}")
        neighbors = [value for day, value in self._offsets.items() if abs((day - broker_date).days) <= 7]
        if neighbors and min(abs(value - offset) for value in neighbors) > 1:
            raise BrokerClockError("Broker offset changed by more than one hour")
        self._offsets[broker_date] = offset
        self._offset_sources[broker_date] = source
        if source in self._VERIFIED_SOURCES:
            self._verified_offset_dates.add(broker_date)

    def _set_timestamp_mode(self, mode: str) -> None:
        if mode not in self._VALID_MODES:
            raise BrokerClockError("invalid MT5 timestamp mode")
        with self._lock:
            if self._timestamp_mode is not None and self._timestamp_mode != mode:
                raise BrokerClockError("MT5 timestamp mode changed unexpectedly")
            self._timestamp_mode = mode

    def _ensure_terminal_connection(self) -> None:
        try:
            terminal_reader = getattr(self._mt5, "terminal_info", None)
            if callable(terminal_reader) and terminal_reader() is None:
                raise BrokerClockUnavailableError("MT5 terminal is unavailable")
            account_reader = getattr(self._mt5, "account_info", None)
            account = account_reader() if callable(account_reader) else None
        except BrokerClockUnavailableError:
            raise
        except Exception as error:
            raise BrokerClockUnavailableError("cannot read MT5 terminal state") from error
        if not callable(account_reader):
            return
        if account is None:
            raise BrokerClockUnavailableError("MT5 account is unavailable")
        identity = (getattr(account, "server", None), getattr(account, "login", None))
        self._activate_identity(identity)

    def _activate_identity(self, identity: tuple[Any, Any]) -> None:
        with self._lock:
            if self._terminal_identity == identity:
                return
            self._offsets.clear()
            self._offset_sources.clear()
            self._verified_offset_dates.clear()
            self._current_offsets.clear()
            self._timestamp_mode = None
            self._terminal_identity = identity
            self._identity_key = self._hash_identity(identity)
        self._load_persisted_cache()

    def _load_persisted_cache(self) -> None:
        payload = self._read_cache_file()
        with self._lock:
            profile = payload.get("profiles", {}).get(self._identity_key or "", {})
            mode = profile.get("timestamp_mode")
            if mode in self._VALID_MODES:
                self._timestamp_mode = mode
            verified_dates = self._parse_cached_dates(profile.get("verified_dates", []))
            for raw_date, raw_offset in profile.get("offsets", {}).items():
                try:
                    broker_date = date.fromisoformat(raw_date)
                    offset = int(raw_offset)
                    source = "restart-verified" if broker_date in verified_dates else "restart-cache"
                    self._store_offset(broker_date, offset, source)
                except (TypeError, ValueError, BrokerClockError):
                    continue

    def _persist_cache(self) -> None:
        if self._cache_path is None or self._identity_key is None:
            return
        with self._cache_write_lock():
            payload = self._read_cache_file()
            payload["version"] = 2
            profiles = payload.setdefault("profiles", {})
            with self._lock:
                existing_profile = profiles.get(self._identity_key, {})
                existing_mode = existing_profile.get("timestamp_mode")
                if existing_mode in self._VALID_MODES and existing_mode != self._timestamp_mode:
                    raise BrokerClockError("cached MT5 timestamp mode conflicts with live calibration")
                merged_offsets = self._merge_cached_offsets(existing_profile.get("offsets", {}))
                verified_dates = self._merge_verified_dates(
                    existing_profile.get("verified_dates", []),
                    merged_offsets,
                )
                profiles[self._identity_key] = {
                    "timestamp_mode": self._timestamp_mode or existing_mode,
                    "offsets": merged_offsets,
                    "verified_dates": verified_dates,
                    "updated_at_utc": datetime.now(timezone.utc).isoformat(),
                }
            self._write_cache_file(payload)

    def _merge_cached_offsets(self, cached_offsets: Any) -> dict[str, int]:
        merged: dict[str, int] = {}
        if isinstance(cached_offsets, dict):
            for raw_date, raw_offset in cached_offsets.items():
                try:
                    broker_date = date.fromisoformat(raw_date)
                    offset = int(raw_offset)
                except (TypeError, ValueError):
                    continue
                if -12 <= offset <= 14:
                    merged[broker_date.isoformat()] = offset
        for broker_date, offset in sorted(self._offsets.items()):
            key = broker_date.isoformat()
            existing = merged.get(key)
            if existing is not None and existing != offset:
                raise BrokerClockError(f"conflicting cached Broker offset for {key}")
            merged[key] = offset
        return merged

    def _merge_verified_dates(
        self,
        cached_dates: Any,
        merged_offsets: dict[str, int],
    ) -> list[str]:
        verified = self._parse_cached_dates(cached_dates) | self._verified_offset_dates
        return sorted(day.isoformat() for day in verified if day.isoformat() in merged_offsets)

    @staticmethod
    def _parse_cached_dates(values: Any) -> set[date]:
        if not isinstance(values, list):
            return set()
        parsed: set[date] = set()
        for value in values:
            try:
                parsed.add(date.fromisoformat(value))
            except (TypeError, ValueError):
                continue
        return parsed

    @contextmanager
    def _cache_write_lock(self):
        if self._cache_path is None:
            yield
            return
        lock_path = self._cache_path.with_name(f"{self._cache_path.name}.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as lock_file:
            lock_file.seek(0, os.SEEK_END)
            if lock_file.tell() == 0:
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _read_cache_file(self) -> dict[str, Any]:
        if self._cache_path is None or not self._cache_path.exists():
            return {"version": 2, "profiles": {}}
        try:
            with self._cache_path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
            return payload if isinstance(payload, dict) else {"version": 2, "profiles": {}}
        except (OSError, ValueError):
            return {"version": 2, "profiles": {}}

    def _write_cache_file(self, payload: dict[str, Any]) -> None:
        if self._cache_path is None:
            return
        self._cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self._cache_path.with_name(
            f"{self._cache_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        try:
            with temp_path.open("w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=False, sort_keys=True)
            os.replace(temp_path, self._cache_path)
        finally:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

    @staticmethod
    def _hash_identity(identity: tuple[Any, Any]) -> str:
        raw = f"{identity[0]}\0{identity[1]}".encode("utf-8", errors="replace")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _validate_observations(observations: list[tuple[date, int]]) -> None:
        for (previous_day, previous), (current_day, current) in zip(observations, observations[1:]):
            if current_day == previous_day and current != previous:
                raise BrokerClockError("conflicting D1 offsets for one Broker date")
            if (current_day - previous_day).days <= 7 and abs(current - previous) > 1:
                raise BrokerClockError("Broker offset changed by more than one hour")

    @staticmethod
    def _offset_from_daily_open(utc_open: datetime) -> int:
        if utc_open.minute or utc_open.second or utc_open.microsecond:
            raise BrokerClockError("D1 bar open is not aligned to a whole UTC hour")
        offset = -utc_open.hour
        if offset < -12:
            offset += 24
        if not -12 <= offset <= 14:
            raise BrokerClockError("derived Broker UTC offset is invalid")
        return offset

    @staticmethod
    def _rate_timestamp(rate: Any) -> float:
        try:
            value = rate["time"]
        except (KeyError, IndexError, TypeError):
            value = getattr(rate, "time", None)
        if value is None:
            raise BrokerClockError("D1 bar has no timestamp")
        return float(value)

    @staticmethod
    def _require_naive_broker_datetime(value: datetime) -> None:
        if value.tzinfo is not None:
            raise BrokerClockError("Broker datetime must be naive")

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            raise BrokerClockError("UTC datetime must be timezone-aware")
        return value.astimezone(timezone.utc)
