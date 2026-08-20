# -*- coding: utf-8 -*-
"""Passive multi-symbol H1 pattern scanner with Telegram delivery state.

The scanner is intentionally independent from Engine5's active-symbol scope.
Exactly one MonitorWorker owns it at a time across all profile worker processes.
Ownership uses the existing XAU scanner OS lock path for rolling compatibility,
while per-symbol alert state prevents replay after worker/process restarts.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import importlib
from pathlib import Path
import sys
from typing import Any, Callable, Iterable

from domain.broker_clock import BrokerClock, BrokerClockError
from domain.file_lock import FileLock
from domain.json_io import JsonStateError, load_json, save_json

ROOT = Path(__file__).resolve().parent.parent
DESKTOP_ROOT = ROOT / "robot-sltp-pro"
DEFAULT_STATE_PATH = ROOT / "xau_h1_pattern_alert_state.json"
DEFAULT_OWNER_LOCK_PATH = ROOT / "xau_h1_pattern_scanner.lock"
TARGET_BASES = ("XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY")
TARGET_PATTERNS = {("T", "G", "G"), ("G", "T", "T")}
H4_TARGET_PATTERNS = {("T", "G"), ("G", "T")}
XAU_FIRST_SCAN_HOUR = 4
FX_FIRST_SCAN_HOUR = 3
EARLIEST_SCAN_HOUR = min(XAU_FIRST_SCAN_HOUR, FX_FIRST_SCAN_HOUR)
LAST_SCAN_HOUR = 17
HISTORY_BARS = 32
STATE_VERSION = 2
PATTERN5_BLOCKS = (3, 6, 9, 12, 15)
REVERSE_GROUPS = {"Sw", "Sr"}
FOLLOW_GROUPS = {"Bt"}


@dataclass(frozen=True, slots=True)
class H1PatternMatch:
    slot_hour: int
    pattern: tuple[str, ...]
    bar_times: tuple[datetime, ...]

    @property
    def pattern_text(self) -> str:
        return " ".join(self.pattern)

    @property
    def bar_range_text(self) -> str:
        return "→".join(f"H{value.hour:02d}" for value in self.bar_times)


@dataclass(frozen=True, slots=True)
class GbpUsdH1SignalContext:
    block_hour: int
    base_hour: int
    base_direction: str | None
    group: str | None
    signal: str | None
    unavailable_reason: str = ""

    @property
    def telegram_line(self) -> str:
        if self.signal and self.base_direction and self.group:
            behavior = "đảo" if self.group in REVERSE_GROUPS else "giữ nguyên"
            return (
                f"• Signal GBPUSD H1: {self.signal} | Base H{self.base_hour:02d}={self.base_direction} | "
                f"Block H{self.block_hour:02d}={self.group} ({behavior})"
            )
        reason = self.unavailable_reason or "chưa đủ dữ liệu"
        return f"• Signal GBPUSD H1: N/A | Base H{self.base_hour:02d} | Block H{self.block_hour:02d} ({reason})"


def pattern5_block_for_h1_slot(slot_hour: int) -> int:
    """Map H03-H17 scanner slots onto the canonical H3/H6/H9/H12/H15 blocks."""
    hour = int(slot_hour)
    if hour < 3 or hour > 17:
        raise ValueError("H1 slot must be between H03 and H17")
    return 3 + ((hour - 3) // 3) * 3


def signal_from_gbpusd_h1_base(direction: str, group: str) -> str:
    """Apply Pattern5 group behavior to one GBPUSD H1 base candle."""
    canonical_direction = str(direction or "").strip().upper()
    canonical_group = str(group or "").strip().title()
    if canonical_direction not in {"T", "G"}:
        raise ValueError(f"Unknown GBPUSD H1 direction: {direction}")
    if canonical_group in REVERSE_GROUPS:
        canonical_direction = "G" if canonical_direction == "T" else "T"
    elif canonical_group not in FOLLOW_GROUPS:
        raise ValueError(f"Unknown Pattern5 group: {group}")
    return "BUY" if canonical_direction == "T" else "SELL"


def resolve_canonical_gbpusd_group(
    mt5_module: Any,
    broker_symbol: str,
    broker_day: date,
    block_hour: int,
) -> str | None:
    """Read GBPUSD's canonical Pattern5 group without duplicating classification rules."""
    if block_hour not in PATTERN5_BLOCKS:
        raise ValueError(f"Unknown Pattern5 block: H{block_hour:02d}")
    desktop_path = str(DESKTOP_ROOT)
    if desktop_path not in sys.path:
        sys.path.insert(0, desktop_path)
    pattern5 = importlib.import_module("pattern5_engine")
    provider_module = importlib.import_module("market_data_provider")
    provider = provider_module.MT5MarketDataProvider(mt5_module)
    offset = pattern5.broker_day_offset(broker_symbol, provider=provider)

    cell, _detail = pattern5.build_signal_cell(
        broker_symbol,
        broker_day,
        block_hour,
        offset,
        provider=provider,
    )
    if not cell:
        return None
    group = str(cell.get("group") or "").strip().title()
    return group if group in (REVERSE_GROUPS | FOLLOW_GROUPS) else None


def resolve_symbol_variant(base: str, symbols: Iterable[Any]) -> str | None:
    """Resolve one base symbol, accepting arbitrary broker suffixes but no prefixes."""
    base_upper = str(base or "").strip().upper()
    if not base_upper:
        return None
    candidates: list[tuple[int, int, str]] = []
    for item in symbols:
        name = str(getattr(item, "name", item) or "").strip()
        upper = name.upper()
        if not upper.startswith(base_upper):
            continue
        exact_rank = 0 if upper == base_upper else 1
        visible_rank = 0 if bool(getattr(item, "visible", False)) else 1
        candidates.append((visible_rank, exact_rank, name))
    if not candidates:
        return None
    candidates.sort(key=lambda row: (row[0], row[1], len(row[2]), row[2].upper()))
    return candidates[0][2]


def resolve_target_symbols(symbols: Iterable[Any]) -> dict[str, str]:
    rows = list(symbols)
    resolved: dict[str, str] = {}
    for base in TARGET_BASES:
        symbol = resolve_symbol_variant(base, rows)
        if symbol:
            resolved[base] = symbol
    return resolved


def resolve_xauusd_symbol(symbols: Iterable[Any]) -> str | None:
    """Backward-compatible helper retained for existing callers/tests."""
    return resolve_symbol_variant("XAUUSD", symbols)


def _rate_value(rate: Any, key: str) -> Any:
    try:
        return rate[key]
    except (KeyError, IndexError, TypeError):
        return getattr(rate, key)


def closed_h1_directions_by_hour(
    rates: Iterable[Any],
    broker_now: datetime,
    decode_time: Callable[[int], datetime],
) -> dict[int, tuple[datetime, str]]:
    """Index fully closed H1 candles from the current broker day by opening hour."""
    current_hour = broker_now.replace(minute=0, second=0, microsecond=0)
    candles: dict[int, tuple[datetime, str]] = {}
    for rate in rates:
        opened = decode_time(int(_rate_value(rate, "time")))
        if opened.tzinfo is not None:
            raise ValueError("decoded MT5 candle time must be naive broker wall time")
        if opened.date() != broker_now.date() or opened >= current_hour:
            continue
        if opened.minute or opened.second or opened.microsecond:
            continue
        direction = "T" if float(_rate_value(rate, "close")) > float(_rate_value(rate, "open")) else "G"
        candles[opened.hour] = (opened, direction)
    return candles


def find_h1_pattern_matches(
    rates: Iterable[Any],
    broker_now: datetime,
    decode_time: Callable[[int], datetime],
    first_scan_hour: int = XAU_FIRST_SCAN_HOUR,
) -> list[H1PatternMatch]:
    """Return eligible backward-looking H1 matches from the current broker day.

    The first scan slot inspects two closed H1 candles newest→oldest and matches
    TG/GT. Later slots through H17 inspect the three latest closed H1 candles
    and match TGG/GTT. XAU starts at H04; FX targets start at H03.
    """
    if broker_now.tzinfo is not None:
        raise ValueError("broker_now must be a naive broker-wall datetime")
    if first_scan_hour not in (FX_FIRST_SCAN_HOUR, XAU_FIRST_SCAN_HOUR):
        raise ValueError("first_scan_hour must be H03 or H04")
    if broker_now.hour < first_scan_hour or broker_now.hour > LAST_SCAN_HOUR:
        return []

    candles = closed_h1_directions_by_hour(rates, broker_now, decode_time)

    matches: list[H1PatternMatch] = []
    for slot_hour in range(first_scan_hour, min(broker_now.hour, LAST_SCAN_HOUR) + 1):
        if slot_hour == first_scan_hour:
            lookback_hours = (slot_hour - 1, slot_hour - 2)
        else:
            lookback_hours = (slot_hour - 1, slot_hour - 2, slot_hour - 3)
        selected = [candles.get(hour) for hour in lookback_hours]
        if any(item is None for item in selected):
            continue
        rows = [item for item in selected if item is not None]
        pattern = tuple(direction for _opened, direction in rows)
        expected = H4_TARGET_PATTERNS if slot_hour == first_scan_hour else TARGET_PATTERNS
        if pattern not in expected:
            continue
        matches.append(H1PatternMatch(slot_hour, pattern, tuple(opened for opened, _direction in rows)))
    return matches


class MultiSymbolH1PatternScanner:
    """One-owner H1 scanner with unlimited per-symbol intraday alerts."""

    def __init__(
        self,
        mt5_module: Any,
        notify: Callable[[str], bool],
        log: Callable[[str], None] | None = None,
        profile_name: str = "",
        state_path: str | Path = DEFAULT_STATE_PATH,
        owner_lock_path: str | Path = DEFAULT_OWNER_LOCK_PATH,
        clock_factory: Callable[..., Any] = BrokerClock,
        lock_factory: Callable[..., Any] = FileLock,
        pattern5_group_resolver: Callable[[Any, str, date, int], str | None] = resolve_canonical_gbpusd_group,
    ) -> None:
        self._mt5 = mt5_module
        self._notify = notify
        self._log = log or (lambda _message: None)
        self._profile_name = str(profile_name or "unknown")
        self._state_path = Path(state_path)
        self._owner_lock_path = Path(owner_lock_path)
        self._clock_factory = clock_factory
        self._lock_factory = lock_factory
        self._pattern5_group_resolver = pattern5_group_resolver
        self._owner_context: Any | None = None
        self._owner_guard: Any | None = None
        self._clock: Any | None = None
        self._symbols: dict[str, str] = {}
        self._gbpusd_symbol: str | None = None
        self._pattern5_group_cache: dict[tuple[str, int], str] = {}
        self._issue_last_logged: dict[str, float] = {}

    @property
    def is_owner(self) -> bool:
        return self._owner_guard is not None

    @property
    def symbol(self) -> str | None:
        """Legacy XAU symbol accessor."""
        return self._symbols.get("XAUUSD")

    @property
    def symbols(self) -> dict[str, str]:
        return dict(self._symbols)

    @property
    def gbpusd_symbol(self) -> str | None:
        return self._gbpusd_symbol

    def _log_issue_once(self, key: str, message: str, now_epoch: float | None = None) -> None:
        import time

        current = time.time() if now_epoch is None else float(now_epoch)
        previous = float(self._issue_last_logged.get(key, 0.0) or 0.0)
        if current - previous >= 300.0:
            self._issue_last_logged[key] = current
            self._log(message)

    def _ensure_owner(self) -> bool:
        if self._owner_guard is not None:
            return True
        try:
            available = self._mt5.symbols_get() or []
        except Exception as error:
            self._log_issue_once("symbols", f"[H1-SCAN] Không đọc được danh sách symbol: {error}")
            return False

        resolved = resolve_target_symbols(available)
        selected: dict[str, str] = {}
        for base, symbol in resolved.items():
            try:
                if self._mt5.symbol_select(symbol, True) is False:
                    self._log_issue_once(f"select:{base}", f"[H1-SCAN] Không select được {symbol}.")
                    continue
                selected[base] = symbol
            except Exception as error:
                self._log_issue_once(f"select:{base}", f"[H1-SCAN] Không select được {symbol}: {error}")
        if not selected:
            self._log_issue_once("targets", "[H1-SCAN] Không tìm thấy/select được symbol mục tiêu hoặc biến thể hậu tố.")
            return False

        gbpusd_symbol = resolve_symbol_variant("GBPUSD", available)
        if gbpusd_symbol:
            try:
                if self._mt5.symbol_select(gbpusd_symbol, True) is False:
                    self._log_issue_once("select:GBPUSD", f"[H1-SCAN] Không select được GBPUSD reference {gbpusd_symbol}.")
                    gbpusd_symbol = None
            except Exception as error:
                self._log_issue_once("select:GBPUSD", f"[H1-SCAN] Không select được GBPUSD reference {gbpusd_symbol}: {error}")
                gbpusd_symbol = None
        else:
            self._log_issue_once("GBPUSD", "[H1-SCAN] Không tìm thấy GBPUSD hoặc biến thể hậu tố để tính Signal GBPUSD H1.")

        owner_context = self._lock_factory(str(self._owner_lock_path), timeout=0.0)
        owner_guard = owner_context.__enter__()
        if owner_guard is None:
            return False
        try:
            clock_symbols = list(selected.values())
            if gbpusd_symbol and gbpusd_symbol not in clock_symbols:
                clock_symbols.append(gbpusd_symbol)
            clock = self._clock_factory(
                mt5_module=self._mt5,
                symbols=tuple(clock_symbols),
                cache_path=str(ROOT / "broker_clock_cache.json"),
            )
        except Exception:
            owner_context.__exit__(None, None, None)
            raise
        self._owner_context = owner_context
        self._owner_guard = owner_guard
        self._clock = clock
        self._symbols = selected
        self._gbpusd_symbol = gbpusd_symbol
        rendered = ", ".join(f"{base}={symbol}" for base, symbol in selected.items())
        gbp_ref = gbpusd_symbol or "N/A"
        self._log(
            f"[H1-SCAN] Scanner owner={self._profile_name} · {rendered} · GBPUSD-ref={gbp_ref} · "
            "XAU H04-H17; FX H03-H17 · first slot=TG/GT, later=TGG/GTT · unlimited alerts; even alerts=caution"
        )
        return True

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        return {"version": STATE_VERSION, "days": {}}

    @staticmethod
    def _validate_alerts(alerts: Any, state_path: Path) -> list[dict[str, Any]]:
        if not isinstance(alerts, list):
            raise ValueError(f"Invalid H1 scanner alerts: {state_path}")
        for alert in alerts:
            if not isinstance(alert, dict) or not isinstance(alert.get("slotHour"), int):
                raise ValueError(f"Invalid H1 scanner alert row: {state_path}")
        return alerts

    def _migrate_v1_state(self, state: dict[str, Any]) -> dict[str, Any]:
        days = state.get("days")
        if not isinstance(days, dict):
            raise ValueError(f"Invalid H1 scanner legacy state: {self._state_path}")
        migrated = self._empty_state()
        for day_key, day_state in days.items():
            if not isinstance(day_key, str) or not isinstance(day_state, dict):
                raise ValueError(f"Invalid H1 scanner legacy day state: {self._state_path}")
            alerts = self._validate_alerts(day_state.get("alerts", []), self._state_path)
            migrated["days"][day_key] = {"symbols": {"XAUUSD": {"alerts": list(alerts)}}}
        return migrated

    def _load_state(self) -> dict[str, Any]:
        state = load_json(str(self._state_path), self._empty_state())
        if not isinstance(state, dict):
            raise ValueError(f"Invalid H1 scanner state: {self._state_path}")
        if state.get("version") == 1:
            state = self._migrate_v1_state(state)
        if state.get("version") != STATE_VERSION or not isinstance(state.get("days"), dict):
            raise ValueError(f"Invalid H1 scanner state: {self._state_path}")
        for day_key, day_state in state["days"].items():
            if not isinstance(day_key, str) or not isinstance(day_state, dict):
                raise ValueError(f"Invalid H1 scanner day state: {self._state_path}")
            symbols = day_state.get("symbols", {})
            if not isinstance(symbols, dict):
                raise ValueError(f"Invalid H1 scanner symbol state: {self._state_path}")
            for base, symbol_state in symbols.items():
                if base not in TARGET_BASES or not isinstance(symbol_state, dict):
                    raise ValueError(f"Invalid H1 scanner symbol row: {self._state_path}")
                self._validate_alerts(symbol_state.get("alerts", []), self._state_path)
        return state

    def _save_state(self, state: dict[str, Any]) -> None:
        days = state.get("days", {})
        if isinstance(days, dict) and len(days) > 14:
            keep = set(sorted(days)[-14:])
            state["days"] = {key: value for key, value in days.items() if key in keep}
        save_json(str(self._state_path), state)

    def _pattern5_group(self, broker_day: date, block_hour: int) -> str | None:
        if not self._gbpusd_symbol:
            return None
        key = (broker_day.isoformat(), int(block_hour))
        cached = self._pattern5_group_cache.get(key)
        if cached:
            return cached
        try:
            group = self._pattern5_group_resolver(
                self._mt5,
                self._gbpusd_symbol,
                broker_day,
                block_hour,
            )
        except Exception as error:
            self._log_issue_once(
                f"gbp-group:{block_hour}",
                f"[H1-SCAN] Không lấy được nhóm Pattern5 GBPUSD H{block_hour:02d}: {error}",
            )
            return None
        canonical = str(group or "").strip().title()
        if canonical in (REVERSE_GROUPS | FOLLOW_GROUPS):
            self._pattern5_group_cache[key] = canonical
            return canonical
        return None

    def _gbpusd_signal_context(
        self,
        slot_hour: int,
        broker_day: date,
        gbp_candles: dict[int, tuple[datetime, str]],
    ) -> GbpUsdH1SignalContext:
        block_hour = pattern5_block_for_h1_slot(slot_hour)
        base_hour = int(slot_hour) - 1
        if not self._gbpusd_symbol:
            return GbpUsdH1SignalContext(block_hour, base_hour, None, None, None, "không có GBPUSD broker")
        base_row = gbp_candles.get(base_hour)
        if base_row is None:
            return GbpUsdH1SignalContext(
                block_hour,
                base_hour,
                None,
                None,
                None,
                f"thiếu GBPUSD H{base_hour:02d} đã đóng",
            )
        _opened, direction = base_row
        group = self._pattern5_group(broker_day, block_hour)
        if not group:
            return GbpUsdH1SignalContext(
                block_hour,
                base_hour,
                direction,
                None,
                None,
                f"H{block_hour:02d} chưa có nhóm canonical",
            )
        signal = signal_from_gbpusd_h1_base(direction, group)
        return GbpUsdH1SignalContext(block_hour, base_hour, direction, group, signal)

    def _message(
        self,
        base: str,
        broker_symbol: str,
        match: H1PatternMatch,
        alert_number: int,
        broker_day: str,
        gbpusd_signal: GbpUsdH1SignalContext,
    ) -> str:
        caution = ""
        if alert_number % 2 == 0:
            caution = f"\n⚠️ CẨN THẬN: Đây là cảnh báo lần {alert_number} của {base} trong ngày."
        return (
            f"🔔 {base} H1 PATTERN #{alert_number}\n"
            f"• Symbol: {broker_symbol}\n"
            f"• Profile: {self._profile_name}\n"
            f"• Ngày broker: {broker_day}\n"
            f"• Mốc scan: H{match.slot_hour:02d}\n"
            f"• Nến xét (mới→cũ): {match.bar_range_text}\n"
            f"• Pattern: {match.pattern_text}\n"
            f"{gbpusd_signal.telegram_line}"
            f"{caution}"
        )

    def scan_once(self) -> int:
        """Scan current broker day across target symbols; return Telegram sends."""
        try:
            if not self._ensure_owner():
                return 0
            assert self._clock is not None
            broker_now = self._clock.now()
            if broker_now.hour < EARLIEST_SCAN_HOUR or broker_now.hour > LAST_SCAN_HOUR:
                return 0

            try:
                state = self._load_state()
            except (JsonStateError, OSError, ValueError) as error:
                self._log_issue_once("state", f"[H1-SCAN] State lỗi, dừng alert để tránh replay: {error}")
                return 0

            timeframe = getattr(self._mt5, "TIMEFRAME_H1", None)
            if timeframe is None:
                self._log_issue_once("timeframe", "[H1-SCAN] MT5 không có TIMEFRAME_H1.")
                return 0

            day_key = broker_now.date().isoformat()
            day_state = state["days"].setdefault(day_key, {"symbols": {}})
            symbol_states = day_state.setdefault("symbols", {})
            sent = 0

            gbp_candles: dict[int, tuple[datetime, str]] = {}
            if self._gbpusd_symbol:
                try:
                    gbp_rates = self._mt5.copy_rates_from_pos(self._gbpusd_symbol, timeframe, 1, HISTORY_BARS)
                except Exception as error:
                    self._log_issue_once("rates:GBPUSD", f"[H1-SCAN] Không lấy được H1 của {self._gbpusd_symbol}: {error}")
                    gbp_rates = None
                if gbp_rates is not None:
                    try:
                        gbp_candles = closed_h1_directions_by_hour(
                            gbp_rates,
                            broker_now,
                            self._clock.broker_datetime_from_mt5_timestamp,
                        )
                    except Exception as error:
                        self._log_issue_once("rates:GBPUSD:decode", f"[H1-SCAN] H1 GBPUSD reference lỗi: {error}")
                else:
                    self._log_issue_once("rates:GBPUSD", f"[H1-SCAN] Không lấy được H1 đã đóng của {self._gbpusd_symbol}.")

            for base, broker_symbol in self._symbols.items():
                symbol_state = symbol_states.setdefault(base, {"alerts": []})
                alerts = symbol_state.setdefault("alerts", [])
                try:
                    rates = self._mt5.copy_rates_from_pos(broker_symbol, timeframe, 1, HISTORY_BARS)
                except Exception as error:
                    self._log_issue_once(f"rates:{base}", f"[H1-SCAN] Không lấy được H1 của {broker_symbol}: {error}")
                    continue
                if rates is None:
                    self._log_issue_once(f"rates:{base}", f"[H1-SCAN] Không lấy được H1 đã đóng của {broker_symbol}.")
                    continue

                first_scan_hour = XAU_FIRST_SCAN_HOUR if base == "XAUUSD" else FX_FIRST_SCAN_HOUR
                matches = find_h1_pattern_matches(
                    rates,
                    broker_now,
                    self._clock.broker_datetime_from_mt5_timestamp,
                    first_scan_hour=first_scan_hour,
                )
                last_slot = max((int(item["slotHour"]) for item in alerts), default=first_scan_hour - 1)
                pending = [match for match in matches if match.slot_hour > last_slot]
                for match in pending:
                    alert_number = len(alerts) + 1
                    gbpusd_signal = self._gbpusd_signal_context(match.slot_hour, broker_now.date(), gbp_candles)
                    message = self._message(base, broker_symbol, match, alert_number, day_key, gbpusd_signal)
                    if not bool(self._notify(message)):
                        self._log_issue_once(
                            f"telegram:{base}",
                            f"[H1-SCAN] {base} match H{match.slot_hour:02d} đang chờ Telegram gửi thành công.",
                        )
                        return sent
                    record = {
                        "slotHour": match.slot_hour,
                        "pattern": match.pattern_text,
                        "bars": [value.isoformat(timespec="minutes") for value in match.bar_times],
                        "symbol": broker_symbol,
                        "profile": self._profile_name,
                        "alertNumber": alert_number,
                        "gbpusdH1Signal": gbpusd_signal.signal or "",
                        "gbpusdBaseHour": gbpusd_signal.base_hour,
                        "gbpusdBaseDirection": gbpusd_signal.base_direction or "",
                        "gbpusdBlockHour": gbpusd_signal.block_hour,
                        "gbpusdGroup": gbpusd_signal.group or "",
                    }
                    alerts.append(record)
                    self._save_state(state)
                    caution_text = " · CẨN THẬN" if alert_number % 2 == 0 else ""
                    self._log(
                        f"[H1-SCAN] {base} đã gửi alert #{alert_number}: "
                        f"H{match.slot_hour:02d} {match.pattern_text}{caution_text}"
                    )
                    sent += 1
            return sent
        except BrokerClockError as error:
            self._log_issue_once("clock", f"[H1-SCAN] Chưa xác định được giờ broker an toàn: {error}")
            return 0
        except Exception as error:
            self._log_issue_once("scan", f"[H1-SCAN] Scan lỗi: {error}")
            return 0

    def close(self) -> None:
        owner_context = self._owner_context
        self._owner_context = None
        self._owner_guard = None
        self._clock = None
        self._symbols = {}
        self._gbpusd_symbol = None
        self._pattern5_group_cache = {}
        if owner_context is not None:
            try:
                owner_context.__exit__(None, None, None)
            except Exception:
                pass


# Compatibility alias for the module/class name introduced by the original XAU-only scanner.
XauH1PatternScanner = MultiSymbolH1PatternScanner
