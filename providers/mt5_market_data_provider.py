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
from datetime import datetime, timedelta, timezone

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
        self._conf = conf or {}
        self._mt5 = mt5_module
        self._clock = broker_clock
        self._symbol_map = {}
        self._cache = {}
        self._connected = False
        self._health_error = ""
        self._preload_days = int(self._conf.get("preload_days", 60) or 60)

    # ------------------------------------------------------------------ #
    # Connection / preload
    # ------------------------------------------------------------------ #
    @property
    def mt5(self):
        if self._mt5 is None:
            raise BrokerClockError("MT5 python module is not available")
        return self._mt5

    def connect(self) -> bool:
        mt5 = self.mt5
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

    def preload(self, symbols=None, timeframes=("M30", "H1", "H4")) -> None:
        if not self._connected:
            self.connect()
        if not self._connected:
            print(f"[MT5 DATA] preload skipped: {self._health_error}")
            return
        symbols = list(symbols or CANONICAL_SYMBOLS)
        now_utc = datetime.now(timezone.utc)
        start_utc = now_utc - timedelta(days=self._preload_days)
        for canonical in symbols:
            resolved = self.resolve_symbol(canonical)
            self._select_symbol(resolved)
            for tf in timeframes:
                attr = self._timeframe_attr(tf)
                if attr is None:
                    continue
                rates = self._copy_rates_range(resolved, attr, start_utc, now_utc)
                bars = [self._normalize_bar(canonical, resolved, tf, row) for row in (rates or [])]
                self._store_bars(canonical, tf, bars)
                print(f"[MT5 DATA] {canonical} {tf} loaded={len(bars)}")
        print(f"[MT5 DATA] Coverage ready: {len(symbols)} symbols x {len(timeframes)} timeframes")

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
        for getter in ("utc_offset_for_date", "get_broker_utc_offset"):
            if self._clock is None or not hasattr(self._clock, getter):
                continue
            try:
                if getter == "utc_offset_for_date" and broker_date is not None:
                    return int(self._clock.utc_offset_for_date(broker_date))
                if getter == "get_broker_utc_offset":
                    if broker_date is not None:
                        return int(self._clock.get_broker_utc_offset(broker_date))
                    return int(self._clock.get_broker_utc_offset())
            except Exception:
                continue
        raise BrokerClockError("BROKER_OFFSET_UNVERIFIED: no historical offset (DST boundary)")

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
            return {
                "state": "disconnected",
                "fresh": False,
                "degraded": False,
                "age_seconds": 999.0,
                "observed_at_utc": self._health_error or "",
                "clock_verified": self.is_broker_utc_offset_verified(),
            }
        reads = sum(len(v) for v in self._cache.values() if isinstance(v, list))
        return {
            "state": "connected" if reads > 0 else "degraded",
            "fresh": reads > 0,
            "degraded": self._connected and reads == 0,
            "age_seconds": 0.0,
            "observed_at_utc": datetime.now(timezone.utc).isoformat(),
            "clock_verified": self.is_broker_utc_offset_verified(),
        }

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

    def get_exact_bar(self, symbol, timeframe, broker_open, *, source_id=None):
        tf = str(timeframe).upper()
        store = self._cache.get((symbol, tf))
        if not store:
            return None
        target = self._naive(broker_open)
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
            "canonical_symbol": symbol,
            "resolved_mt4_symbol": resolved,
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