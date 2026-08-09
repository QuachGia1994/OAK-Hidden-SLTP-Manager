# -*- coding: utf-8 -*-
"""MetaTrader 5 market-data provider for the OAK Signal engine.

Default ``MarketDataProvider``.  Reads M30/H1/H4 completed candles and the
Broker clock directly from the MT5 Python API.  MT5 rate timestamps are
interpreted as UTC and converted to Broker time using a calibrated
``BrokerClock``.

Raw ``numpy.void`` and numpy scalar rows are normalized to plain ``dict``
scalars before property access, so the historical ``'numpy.void' object has no
attribute 'get'`` failure mode is impossible.
"""
from __future__ import annotations

import os
import concurrent.futures
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from providers.health_contract import MarketDataHealth

CANONICAL_SYMBOLS = ("XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD")
SUFFIX_CANDIDATES = ("+", ".a", ".i", "m", ".m", "c", ".c", "#", ".")
PREFIX_CANDIDATES = (".",)

_TIMEFRAME_ATTR = {
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
}
_TIMEFRAME_DELTA = {
    "M30": timedelta(minutes=30),
    "H1": timedelta(hours=1),
    "H4": timedelta(hours=4),
}


@dataclass
class PreloadResult:
    """Result of a provider preload pass (coverage, account, terminal)."""

    attempted: int
    loaded: int
    missing: list
    complete: bool
    account: int | None
    server: str
    terminal_path: str


class BrokerClockError(Exception):
    """Raised when the Broker clock or a historical offset is unavailable."""


def _scalar(value, default=0.0):
    if value is None:
        return default
    if hasattr(value, "item"):
        try:
            value = value.item()
        except (TypeError, ValueError):
            pass
    return value


def _to_float(value, default=0.0):
    try:
        return float(_scalar(value, default))
    except (TypeError, ValueError):
        return default


def _to_int(value, default=0):
    try:
        return int(_scalar(value, default))
    except (TypeError, ValueError):
        return default


def _fmt_price(value):
    v = _to_float(value, None) if value is not None else _to_float(value)
    if value is None:
        return ""
    return f"{v:.6f}"


def _read_field(row, field):
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(field)
    try:
        value = row[field]
    except (KeyError, IndexError, TypeError, ValueError):
        try:
            value = getattr(row, field, None)
        except Exception:
            value = None
    return value


class MT5MarketDataProvider:
    """``MarketDataProvider`` reading completed bars and clock from MT5."""

    name = "MT5"

    def __init__(self, mt5_module=None, broker_clock=None, conf=None):
        self._conf = dict(conf or {})
        self._mt5 = mt5_module
        self._clock = broker_clock
        self._symbol_map = {}
        self._cache = {}
        self._connected = False
        self._health_error = ""
        self._profile_cfg = {}
        self._preload_days = int(os.environ.get("MT5_PRELOAD_DAYS", self._conf.get("preload_days", 50)) or 50)
        self._last_preload_ok_utc = None

    # ------------------------------------------------------------------ #
    # Connection / preload
    # ------------------------------------------------------------------ #
    @property
    def mt5(self):
        if self._mt5 is None:
            raise BrokerClockError("MT5 python module is not available")
        return self._mt5

    def bind_profile(self, profile_cfg):
        """Attach one selected profile's terminal/login/server to this provider.

        After ``ensure_mt5_profile_connected`` has attached a session, this
        records the profile so ``connect()`` reuses that session instead of
        re-initializing a different/global terminal path.
        """
        self._profile_cfg = dict(profile_cfg or {})
        path = str(self._profile_cfg.get("path", "") or "").strip()
        if path:
            self._conf["mt5_path"] = path
        return self

    def _session_matches_profile(self) -> bool:
        mt5 = self.mt5
        try:
            tinfo = mt5.terminal_info()
            account = mt5.account_info()
            if tinfo is None or account is None:
                return False
            expected_login = self._profile_cfg.get("login_id", self._profile_cfg.get("login"))
            expected_server = self._profile_cfg.get("server", self._profile_cfg.get("broker"))
            if expected_login not in (None, ""):
                try:
                    if int(getattr(account, "login", 0)) != int(expected_login):
                        return False
                except (TypeError, ValueError):
                    return False
            if expected_server:
                actual = str(getattr(account, "server", getattr(account, "company", "")))
                if str(expected_server).lower() not in actual.lower():
                    return False
            return True
        except Exception:
            return False

    def connect(self, reuse_existing_session=True) -> bool:
        mt5 = self.mt5
        if reuse_existing_session:
            try:
                if mt5.terminal_info() is not None and mt5.account_info() is not None:
                    if self._session_matches_profile():
                        self._connected = True
                        self._health_error = ""
                        return True
            except Exception:
                pass
        try:
            path = self._conf.get("mt5_path", "") if isinstance(self._conf, dict) else ""
            if path and os.path.exists(path):
                ok = mt5.initialize(path)
            else:
                ok = mt5.initialize()
            if not ok:
                err = getattr(mt5, "last_error", lambda: "")()
                self._health_error = str(err)
                self._connected = False
                return False
            try:
                if mt5.terminal_info() is None:
                    self._health_error = "MT5 terminal_info() returned None"
                    self._connected = False
                    return False
                if mt5.account_info() is None:
                    self._health_error = "MT5 account_info() returned None"
                    self._connected = False
                    return False
                if not self._session_matches_profile():
                    self._health_error = "Connected MT5 terminal does not match selected profile"
                    self._connected = False
                    return False
            except Exception as exc:
                self._health_error = str(exc)
                self._connected = False
                return False
            self._connected = True
            self._health_error = ""
            return True
        except Exception as exc:
            self._health_error = str(exc)
            self._connected = False
            return False

    def resolve_symbol(self, canonical: str) -> str:
        if canonical in self._symbol_map:
            return self._symbol_map[canonical]
        mt5 = self.mt5
        if not hasattr(mt5, "symbol_info"):
            self._symbol_map[canonical] = canonical
            return canonical
        try:
            resolved = None
            try:
                if mt5.symbol_info(canonical) is not None:
                    resolved = canonical
            except Exception:
                pass
            if resolved is None:
                for suffix in SUFFIX_CANDIDATES:
                    try:
                        if mt5.symbol_info(canonical + suffix) is not None:
                            resolved = canonical + suffix
                            break
                    except Exception:
                        continue
            if resolved is None:
                for prefix in PREFIX_CANDIDATES:
                    try:
                        if mt5.symbol_info(prefix + canonical) is not None:
                            resolved = prefix + canonical
                            break
                    except Exception:
                        continue
            if resolved is None:
                resolved = canonical
            self._symbol_map[canonical] = resolved
            return resolved
        except Exception:
            self._symbol_map[canonical] = canonical
            return canonical

    def _timeframe_attr(self, timeframe):
        attr = _TIMEFRAME_ATTR.get(str(timeframe).upper())
        if not attr:
            return None
        value = getattr(self.mt5, attr, None)
        return value if isinstance(value, int) else None

    def _select_symbol(self, resolved: str) -> bool:
        mt5 = self.mt5
        if hasattr(mt5, "symbol_select"):
            try:
                return bool(mt5.symbol_select(resolved, True))
            except Exception:
                return False
        return True

    def preload(self, symbols=None, timeframes=("M30", "H1", "H4"), days=None) -> "PreloadResult":
        if not self._connected:
            self.connect()
        if not self._connected:
            print(f"[MT5 DATA] preload skipped: {self._health_error}")
            return PreloadResult(0, 0, [], False, None, "", "")
        symbols = list(symbols or CANONICAL_SYMBOLS)
        preload_days = int(days or self._preload_days or 14)
        timeout_seconds = int(os.environ.get("MT5_COPY_RATES_TIMEOUT_SECONDS", "15") or 15)
        now_utc = datetime.now(timezone.utc)
        start_utc = now_utc - timedelta(days=preload_days)
        missing = []
        loaded_total = 0
        print(f"[MT5 DATA] preload starting: connected={self._connected}, symbols={symbols}, timeframes={timeframes}, days={preload_days}")
        for canonical in symbols:
            resolved = self.resolve_symbol(canonical)
            self._select_symbol(resolved)
            for tf in timeframes:
                attr = self._timeframe_attr(tf)
                if attr is None:
                    missing.append(f"{canonical} {tf}")
                    continue
                try:
                    print(f"[MT5 DATA] fetching {canonical} {tf}...")
                    rates = self._copy_rates_range_with_timeout(
                        resolved, attr, start_utc, now_utc, timeout_seconds
                    )
                    rows = rates if rates is not None and len(rates) > 0 else []
                    bars = [self._normalize_bar(canonical, resolved, tf, row) for row in rows]
                    self._store_bars(canonical, tf, bars)
                    loaded_total += len(bars)
                    print(f"[MT5 DATA] {canonical} {tf} loaded={len(bars)}")
                    if not bars:
                        missing.append(f"{canonical} {tf}")
                except TimeoutError:
                    missing.append(f"{canonical} {tf}")
                    print(f"[MT5 DATA] {canonical} {tf} timed out after {timeout_seconds}s")
                except Exception as exc:
                    missing.append(f"{canonical} {tf}")
                    print(f"[MT5 DATA] {canonical} {tf} failed: {exc}")
        account = None
        server = ""
        terminal_path = ""
        try:
            account = self.mt5.account_info()
            server = str(getattr(account, "server", "") or "")
            account = getattr(account, "login", None)
        except Exception:
            pass
        try:
            terminal_path = str(self._conf.get("mt5_path", "") or "")
        except Exception:
            pass
        complete = not missing
        if complete or (loaded_total > 0 and len(missing) < len(symbols) * len(timeframes)):
            self._last_preload_ok_utc = datetime.now(timezone.utc)
        if complete:
            print(f"[MT5 DATA] Coverage ready: {len(symbols)} symbols x {len(timeframes)} timeframes")
        else:
            print(f"[MT5 DATA] Coverage incomplete ({len(symbols) * len(timeframes) - len(missing)}/{len(symbols) * len(timeframes)}):")
            for item in missing:
                print(f"[MT5 DATA]   {item} = 0")
        return PreloadResult(
            attempted=len(symbols) * len(timeframes),
            loaded=loaded_total,
            missing=missing,
            complete=complete,
            account=account,
            server=server,
            terminal_path=terminal_path,
        )

    def _copy_rates_range(self, resolved, attr, start_utc, end_utc):
        mt5 = self.mt5
        if not hasattr(mt5, "copy_rates_range"):
            return None
        try:
            rates = mt5.copy_rates_range(resolved, attr, start_utc, end_utc)
        except Exception:
            try:
                mt5.symbol_select(resolved, True)
            except Exception:
                pass
            rates = None
        if rates is not None and len(rates) == 0:
            print(f"[MT5 DATA] {resolved} empty history; mt5.last_error={getattr(mt5, 'last_error', lambda: '')()}")
        return rates

    def _copy_rates_range_with_timeout(self, resolved, attr, start_utc, end_utc, timeout_seconds):
        """Run _copy_rates_range in a worker thread; abort on timeout.

        A hung MT5 terminal (downloading history from broker) can block
        copy_rates_range indefinitely. Submitting it via a ThreadPoolExecutor
        and calling result(timeout=...) lets us give up after
        ``timeout_seconds`` so preload and the rest of main() stay responsive.

        ``shutdown(wait=False, cancel_futures=True)`` lets the still-running
        worker thread be abandoned (daemon) rather than blocking the caller.
        """
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(self._copy_rates_range, resolved, attr, start_utc, end_utc)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            future.cancel()
            raise TimeoutError(f"copy_rates_range timed out after {timeout_seconds}s") from exc
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _store_bars(self, canonical, tf, bars):
        key = (canonical, tf.upper())
        existing = self._cache.setdefault(key, [])
        seen = {(b.get("time")) for b in existing}
        for bar in bars:
            ts = bar.get("time")
            if ts is not None and ts in seen:
                continue
            seen.add(ts)
            existing.append(bar)
        existing.sort(key=lambda b: b.get("time") or 0)

    # ------------------------------------------------------------------ #
    # Broker clock / health
    # ------------------------------------------------------------------ #
    def get_broker_now(self):
        if self._clock is not None and hasattr(self._clock, "now"):
            return self._clock.now()
        mt5 = self.mt5
        try:
            tinfo = mt5.terminal_info()
            if tinfo is not None and getattr(tinfo, "time", None) is not None:
                return datetime.fromtimestamp(int(tinfo.time)).replace(tzinfo=None)
        except Exception:
            pass
        try:
            tick = mt5.symbol_info_tick("XAUUSD")
            if tick is not None and getattr(tick, "time", None) is not None:
                return datetime.fromtimestamp(int(tick.time)).replace(tzinfo=None)
        except Exception:
            pass
        raise BrokerClockError("MT5 terminal clock unavailable")

    def get_broker_utc_offset(self, broker_date=None, **kwargs) -> int:
        errors: list[Exception] = []
        for getter in ("utc_offset_for_date", "current_utc_offset", "get_broker_utc_offset"):
            if self._clock is None or not hasattr(self._clock, getter):
                continue
            try:
                if getter == "utc_offset_for_date" and broker_date is not None:
                    return int(self._clock.utc_offset_for_date(broker_date))
                if getter == "current_utc_offset":
                    # ``current_utc_offset`` carries a cache fallback that
                    # survives transient calibration / D1 history failures, so
                    # it can keep serving the live broker offset when
                    # ``utc_offset_for_date`` raises (intermittent tick stall,
                    # D1 timeout, side-effect of ``configure_symbols``).
                    # Only accept the result when the caller asked for the
                    # current broker day; for historical dates, fall through to
                    # the legacy getters so we never substitute today's offset
                    # for a past date (which would cross DST boundaries).
                    now_utc = datetime.now(timezone.utc)
                    broker_offset_now = int(self._clock.current_utc_offset(now_utc))
                    if broker_date is None:
                        return broker_offset_now
                    # The clock's verification state is authoritative for the
                    # requested broker date. This preserves the live cached
                    # offset after a transient historical lookup failure while
                    # still refusing to substitute today's offset for an
                    # unverified historical date.
                    if self.is_broker_utc_offset_verified(broker_date):
                        return broker_offset_now
                    broker_today = (now_utc + timedelta(hours=broker_offset_now)).date()
                    if broker_today == broker_date:
                        return broker_offset_now
                    continue
                if getter == "get_broker_utc_offset":
                    if broker_date is not None:
                        return int(self._clock.get_broker_utc_offset(broker_date))
                    return int(self._clock.get_broker_utc_offset())
            except Exception as error:
                errors.append(error)
                continue
        raise BrokerClockError(
            "BROKER_OFFSET_UNVERIFIED: no historical offset (DST boundary)"
        ) from (errors[-1] if errors else None)

    def is_broker_utc_offset_verified(self, broker_date=None) -> bool:
        if self._clock is None:
            return False
        getter = getattr(self._clock, "is_broker_utc_offset_verified", None)
        if not callable(getter):
            return True
        try:
            return bool(getter(broker_date) if broker_date is not None else getter())
        except Exception:
            return False

    def get_health(self):
        if not self._connected:
            return MarketDataHealth(
                state="disconnected",
                fresh=False,
                degraded=False,
                age_seconds=999.0,
                observed_at_utc="",
                clock_verified=self.is_broker_utc_offset_verified(),
                error=self._health_error,
            )
        now_utc = datetime.now(timezone.utc)
        fresh_age_limit = timedelta(hours=int(os.environ.get("MT5_HEALTH_FRESH_HOURS", "8") or 8))
        fresh = self._last_preload_ok_utc is not None and (now_utc - self._last_preload_ok_utc) <= fresh_age_limit
        return MarketDataHealth(
            state="connected" if self._last_preload_ok_utc is not None else "degraded",
            fresh=fresh,
            degraded=self._connected and (self._last_preload_ok_utc is None or not fresh),
            age_seconds=0.0,
            observed_at_utc=datetime.now(timezone.utc).isoformat(),
            clock_verified=self.is_broker_utc_offset_verified(),
            error=self._health_error,
        )

    # ------------------------------------------------------------------ #
    # Bar access (Signal engine contract)
    # ------------------------------------------------------------------ #
    def get_bars(self, symbol, timeframe, start_broker, end_broker):
        tf = str(timeframe).upper()
        store = self._cache.get((symbol, tf))
        if not store:
            return []
        if tf not in ("M30", "H1", "H4"):
            return list(store)
        s = self._naive(start_broker)
        e = self._naive(end_broker)
        out = []
        for bar in store:
            open_dt = bar.get("broker_dt")
            if open_dt is None:
                continue
            odt = self._naive(open_dt)
            if s <= odt <= e:
                out.append(bar)
        return out

    def fetch_historical_bars(self, symbol, timeframe, start_broker, end_broker, timeout_seconds=None):
        """Fetch bars for a broker-time window directly from MT5 and cache them.

        The in-memory cache only spans a bounded preload window (``_preload_days``).
        Historical rebuild / D-Direction lookups may need bars older than that
        window.  This method calls ``copy_rates_range`` for the exact range and
        stores the normalized bars into ``self._cache`` so subsequent
        ``get_bars``/``get_exact_bar`` calls can serve them, then returns the
        normalized bars covering the requested window.
        """
        if not self._connected:
            self.connect()
        if not self._connected:
            return []
        tf = str(timeframe).upper()
        attr = self._timeframe_attr(tf)
        if attr is None:
            return []
        resolved = self.resolve_symbol(symbol)
        self._select_symbol(resolved)
        timeout = int(timeout_seconds or os.environ.get("MT5_COPY_RATES_TIMEOUT_SECONDS", "15") or 15)
        s = self._naive(start_broker)
        e = self._naive(end_broker)
        # Convert broker-time window to UTC using the broker offset for the start date.
        # Use a small margin to cover DST edge effects.
        offset_hours = 0
        if self._clock is not None:
            try:
                if hasattr(self._clock, "utc_offset_for_date"):
                    offset_hours = int(self._clock.utc_offset_for_date(s.date()))
                elif hasattr(self._clock, "get_broker_utc_offset"):
                    offset_hours = int(self._clock.get_broker_utc_offset(s.date()))
            except Exception:
                offset_hours = 0
        # broker_dt = utc + offset -> utc = broker_dt - offset
        start_utc = s - timedelta(hours=offset_hours) - timedelta(hours=1)
        end_utc = e - timedelta(hours=offset_hours) + timedelta(hours=25)
        rates = self._copy_rates_range_with_timeout(resolved, attr, start_utc, end_utc, timeout)
        rows = rates if rates is not None and len(rates) > 0 else []
        bars = [self._normalize_bar(symbol, resolved, tf, row) for row in rows]
        self._store_bars(symbol, tf, bars)
        return self.get_bars(symbol, tf, s, e)

    def get_exact_bar(self, symbol, timeframe, broker_open, *, source_id=None):
        tf = str(timeframe).upper()
        target = self._naive(broker_open)
        store = self._cache.get((symbol, tf))
        if store:
            for bar in store:
                open_dt = bar.get("broker_dt")
                if open_dt is not None and self._naive(open_dt) == target:
                    return bar

        # Cache miss: attempt a one-shot on-demand fetch for the bar's window.
        # This repairs bars that completed after the startup preload ran (for
        # example H3's M30 layer candles that close at 02:30/03:00 Broker while
        # preload only sampled earlier bars).  The live eval path passes no
        # ``source_id``; offline rebuild that needs explicit source selection
        # is left untouched.  Failure is swallowed: callers keep the previous
        # "MISSING" behavior, but a successful fetch populates the cache so a
        # retry through ``get_bars``/``get_exact_bar`` finds the bar.
        if source_id is None and self._connected and hasattr(self, "fetch_historical_bars"):
            try:
                tf_delta = _TIMEFRAME_DELTA.get(tf, timedelta(minutes=30))
                self.fetch_historical_bars(symbol, tf, broker_open, broker_open + tf_delta)
            except Exception:
                pass
            store = self._cache.get((symbol, tf))
            if store:
                for bar in store:
                    open_dt = bar.get("broker_dt")
                    if open_dt is not None and self._naive(open_dt) == target:
                        return bar
        return None

    def get_active_source_id(self, max_age_seconds: int = 60):
        return "mt5" if self._connected else None

    def clear(self):
        self._cache.clear()

    # ------------------------------------------------------------------ #
    # Internal normalization
    # ------------------------------------------------------------------ #
    def _normalize_bar(self, canonical, resolved, tf, row):
        ts = _to_int(_read_field(row, "time"))
        utc_open = datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None
        broker_offset = self._compute_offset(utc_open.date() if utc_open is not None else None)
        broker_dt = None
        if utc_open is not None and broker_offset is not None:
            broker_dt = (utc_open + timedelta(hours=broker_offset)).replace(tzinfo=None)

        open_val = _to_float(_read_field(row, "open"))
        high_val = _to_float(_read_field(row, "high"))
        low_val = _to_float(_read_field(row, "low"))
        close_val = _to_float(_read_field(row, "close"))
        tick = _to_int(_read_field(row, "tick_volume"))

        return {
            "time": ts,
            "open": open_val,
            "high": high_val,
            "low": low_val,
            "close": close_val,
            "open_exact": _fmt_price(open_val),
            "high_exact": _fmt_price(high_val),
            "low_exact": _fmt_price(low_val),
            "close_exact": _fmt_price(close_val),
            "tick_volume": tick,
            "broker_dt": broker_dt,
            "utc_open_at": utc_open.astimezone(timezone.utc).isoformat() if utc_open else "",
            "is_complete": True,
            "canonical_symbol": canonical,
            "resolved_symbol": resolved,
            "timeframe": tf,
            "source_id": "mt5",
        }

    def _compute_offset(self, utc_date=None):
        if self._clock is None:
            return None
        for getter in ("utc_offset_for_date", "get_broker_utc_offset"):
            if not hasattr(self._clock, getter):
                continue
            try:
                if getter == "utc_offset_for_date" and utc_date is not None:
                    return int(self._clock.utc_offset_for_date(utc_date))
                if utc_date is not None:
                    return int(self._clock.get_broker_utc_offset(utc_date))
                return int(self._clock.get_broker_utc_offset())
            except Exception:
                continue
        return None

    @staticmethod
    def _naive(value):
        return value.replace(tzinfo=None) if getattr(value, "tzinfo", None) else value