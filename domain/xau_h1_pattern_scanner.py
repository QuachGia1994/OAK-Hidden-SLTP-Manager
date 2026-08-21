# -*- coding: utf-8 -*-
"""Passive H1 fallback scanner mirroring the cTrader cloud scanner.

Pattern detection uses AUDUSD for XAUUSD, GBPUSD for EURUSD/AUDUSD, and each target itself for USDCAD/USDJPY. Target signals combine that source pattern with the configured closed H1 base candle from the current broker day only. Exactly one local MonitorWorker may own this fallback scanner through the existing OS-backed lock.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Callable, Iterable

from domain.broker_clock import BrokerClock, BrokerClockError
from domain.file_lock import FileLock
from domain.json_io import JsonStateError, load_json, save_json

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE_PATH = ROOT / "xau_h1_pattern_alert_state.json"
DEFAULT_OWNER_LOCK_PATH = ROOT / "xau_h1_pattern_scanner.lock"

TARGET_BASES = ("XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY")
SCANNER_BASES = ("AUDUSD", "GBPUSD", "USDCAD", "USDJPY")
REQUIRED_HISTORY_BASES = ("GBPUSD", "AUDUSD", "EURUSD", "USDCAD", "USDJPY")

TWO_CANDLE_SW_PATTERNS = {("T", "G"), ("G", "T")}
PURE_SW_3_PATTERNS = {("T", "G", "G"), ("G", "T", "T")}
NORMAL_SW_3_PATTERNS = {("T", "T", "T"), ("G", "G", "G")}

PATTERN_KIND_SW2 = "sw2"
PATTERN_KIND_SW3_PURE = "sw3Pure"
PATTERN_KIND_SW3_NORMAL = "sw3Normal"
PATTERN_KINDS = {PATTERN_KIND_SW2, PATTERN_KIND_SW3_PURE, PATTERN_KIND_SW3_NORMAL}
PATTERN_LABELS = {
    PATTERN_KIND_SW2: "SW 2 cây",
    PATTERN_KIND_SW3_PURE: "SW 3 cây thuần",
    PATTERN_KIND_SW3_NORMAL: "SW 3 cây thường",
}
INVERTED_PATTERN_TARGETS = {"USDCAD", "USDJPY"}

EARLIEST_SCAN_HOUR = 3
LAST_SCAN_HOUR = 17
HISTORY_BARS = 32
STATE_VERSION = 7


@dataclass(frozen=True, slots=True)
class H1PatternMatch:
    slot_hour: int
    pattern: tuple[str, ...]
    bar_times: tuple[datetime, ...]
    pattern_kind: str

    @property
    def pattern_text(self) -> str:
        return " ".join(self.pattern)

    @property
    def bar_range_text(self) -> str:
        return "→".join(f"H{value.hour:02d}" for value in self.bar_times)

    @property
    def pattern_label(self) -> str:
        return PATTERN_LABELS.get(self.pattern_kind, self.pattern_kind)


@dataclass(frozen=True, slots=True)
class H1BaseSignalContext:
    base_symbol: str
    base_hour: int
    base_direction: str | None
    signal: str | None
    unavailable_reason: str = ""

    @property
    def telegram_line(self) -> str:
        if self.signal and self.base_direction:
            return (
                f"• Base H1: {self.base_symbol} H{self.base_hour:02d}="
                f"{self.base_direction} → {self.signal}"
            )
        reason = self.unavailable_reason or "chưa đủ dữ liệu"
        return f"• Base H1: {self.base_symbol} H{self.base_hour:02d} N/A ({reason})"


def signal_from_h1_direction(direction: str) -> str:
    canonical = str(direction or "").strip().upper()
    if canonical == "T":
        return "BUY"
    if canonical == "G":
        return "SELL"
    raise ValueError(f"Unknown H1 direction: {direction}")


def pattern_follows_base(base: str, pattern_kind: str) -> bool:
    canonical = str(base or "").upper()
    if pattern_kind not in PATTERN_KINDS:
        raise ValueError(f"Unknown H1 pattern kind: {pattern_kind}")
    if canonical in INVERTED_PATTERN_TARGETS:
        return pattern_kind != PATTERN_KIND_SW2
    return pattern_kind == PATTERN_KIND_SW2


def signal_from_pattern_base(base: str, base_signal: str, pattern_kind: str) -> str:
    signal = str(base_signal or "").strip().upper()
    if signal not in {"BUY", "SELL"}:
        raise ValueError("H1 base signal must be BUY or SELL")
    if pattern_follows_base(base, pattern_kind):
        return signal
    return "SELL" if signal == "BUY" else "BUY"


def signal_from_gbpusd_pattern(gbpusd_signal: str, pattern_kind: str) -> str:
    """Legacy XAUUSD alias kept for compatibility with older callers."""
    return signal_from_pattern_base("XAUUSD", gbpusd_signal, pattern_kind)


def scanner_base_for_target(base: str) -> str:
    canonical = str(base or "").upper()
    if canonical == "XAUUSD":
        return "AUDUSD"
    if canonical in INVERTED_PATTERN_TARGETS:
        return canonical
    return "GBPUSD"


def base_symbol_for_target(base: str) -> str:
    canonical = str(base or "").upper()
    return "GBPUSD" if canonical in {"XAUUSD", *INVERTED_PATTERN_TARGETS} else canonical


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


def _rows_for_hours(
    candles: dict[int, tuple[datetime, str]],
    hours: tuple[int, ...],
) -> list[tuple[datetime, str]] | None:
    selected = [candles.get(hour) for hour in hours]
    if any(item is None for item in selected):
        return None
    return [item for item in selected if item is not None]


def _matches_from_candles(
    candles: dict[int, tuple[datetime, str]],
    broker_hour: int,
) -> list[H1PatternMatch]:
    matches: list[H1PatternMatch] = []
    last_slot = min(int(broker_hour), LAST_SCAN_HOUR)
    previous_accepted_pure_slot: int | None = None
    for slot_hour in range(EARLIEST_SCAN_HOUR, last_slot + 1):
        if slot_hour == EARLIEST_SCAN_HOUR:
            rows2 = _rows_for_hours(candles, (2, 1))
            if not rows2:
                continue
            pattern2 = tuple(direction for _opened, direction in rows2)
            if pattern2 in TWO_CANDLE_SW_PATTERNS:
                matches.append(H1PatternMatch(
                    slot_hour,
                    pattern2,
                    tuple(opened for opened, _direction in rows2),
                    PATTERN_KIND_SW2,
                ))
            continue

        rows3 = _rows_for_hours(candles, tuple(slot_hour - offset for offset in range(1, 4)))
        if not rows3:
            continue
        pattern3 = tuple(direction for _opened, direction in rows3)
        if pattern3 in PURE_SW_3_PATTERNS:
            if previous_accepted_pure_slot is not None and slot_hour - previous_accepted_pure_slot == 2:
                previous_accepted_pure_slot = None
                continue
            matches.append(H1PatternMatch(
                slot_hour,
                pattern3,
                tuple(opened for opened, _direction in rows3),
                PATTERN_KIND_SW3_PURE,
            ))
            previous_accepted_pure_slot = slot_hour
            continue
        if pattern3 not in NORMAL_SW_3_PATTERNS:
            continue
        older = candles.get(slot_hour - 4)
        if older is not None and older[1] == pattern3[0]:
            continue
        matches.append(H1PatternMatch(
            slot_hour,
            pattern3,
            tuple(opened for opened, _direction in rows3),
            PATTERN_KIND_SW3_NORMAL,
        ))
    return matches


def find_h1_pattern_matches(
    rates: Iterable[Any],
    broker_now: datetime,
    decode_time: Callable[[int], datetime],
    first_scan_hour: int = EARLIEST_SCAN_HOUR,
) -> list[H1PatternMatch]:
    """Find current H1 source patterns newest→oldest on AUDUSD/GBPUSD."""
    if broker_now.tzinfo is not None:
        raise ValueError("broker_now must be a naive broker-wall datetime")
    if int(first_scan_hour) != EARLIEST_SCAN_HOUR:
        raise ValueError("H1 scanner starts at H03")
    if broker_now.hour < EARLIEST_SCAN_HOUR or broker_now.hour > LAST_SCAN_HOUR:
        return []
    candles = closed_h1_directions_by_hour(rates, broker_now, decode_time)
    return _matches_from_candles(candles, broker_now.hour)


def pattern_kind_from_text(pattern_text: str) -> str | None:
    pattern = tuple(str(pattern_text or "").strip().upper().split())
    if pattern in TWO_CANDLE_SW_PATTERNS:
        return PATTERN_KIND_SW2
    if pattern in PURE_SW_3_PATTERNS:
        return PATTERN_KIND_SW3_PURE
    if pattern in NORMAL_SW_3_PATTERNS:
        return PATTERN_KIND_SW3_NORMAL
    return None


class MultiSymbolH1PatternScanner:
    """One-owner MT5 fallback mirroring cloud scanner v7 semantics."""

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
        publish_state: Callable[[dict[str, Any], str], Any] | None = None,
    ) -> None:
        self._mt5 = mt5_module
        self._notify = notify
        self._log = log or (lambda _message: None)
        self._profile_name = str(profile_name or "unknown")
        self._state_path = Path(state_path)
        self._owner_lock_path = Path(owner_lock_path)
        self._clock_factory = clock_factory
        self._lock_factory = lock_factory
        self._publish_state = publish_state
        self._last_published_signature: str | None = None
        self._publish_retry_after = 0.0
        self._owner_context: Any | None = None
        self._owner_guard: Any | None = None
        self._clock: Any | None = None
        self._symbols: dict[str, str] = {}
        self._gbpusd_symbol: str | None = None
        self._issue_last_logged: dict[str, float] = {}

    @property
    def is_owner(self) -> bool:
        return self._owner_guard is not None

    @property
    def symbol(self) -> str | None:
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

        gbpusd_symbol = resolve_symbol_variant("GBPUSD", available)
        if gbpusd_symbol:
            try:
                if self._mt5.symbol_select(gbpusd_symbol, True) is False:
                    gbpusd_symbol = None
            except Exception:
                gbpusd_symbol = None
        if not selected or not gbpusd_symbol or "AUDUSD" not in selected:
            self._log_issue_once(
                "required-symbols",
                "[H1-SCAN] Thiếu target/AUDUSD/GBPUSD broker symbol; fallback scanner dừng fail-closed.",
            )
            return False

        owner_context = self._lock_factory(str(self._owner_lock_path), timeout=0.0)
        owner_guard = owner_context.__enter__()
        if owner_guard is None:
            return False
        try:
            clock_symbols = list(dict.fromkeys([*selected.values(), gbpusd_symbol]))
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
        self._log(
            f"[H1-SCAN] fallback owner={self._profile_name} · {rendered} · GBPUSD={gbpusd_symbol} · "
            "patternSources=XAU:AUDUSD,EUR/AUD:GBPUSD,CAD/JPY:self · H03-H17 · emit=SW2,SW3-pure,SW3-normal · no-post-check"
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

    def _migrate_legacy_state(self, state: dict[str, Any]) -> dict[str, Any]:
        days = state.get("days")
        if not isinstance(days, dict):
            raise ValueError(f"Invalid H1 scanner legacy state: {self._state_path}")
        migrated = self._empty_state()
        for day_key, day_state in days.items():
            if not isinstance(day_key, str) or not isinstance(day_state, dict):
                continue
            max_slot = 0
            if state.get("version") == 1:
                alerts = day_state.get("alerts", [])
                if isinstance(alerts, list):
                    max_slot = max((int(row.get("slotHour", 0)) for row in alerts if isinstance(row, dict)), default=0)
            else:
                symbols = day_state.get("symbols", {})
                if isinstance(symbols, dict):
                    for symbol_state in symbols.values():
                        if not isinstance(symbol_state, dict):
                            continue
                        alerts = symbol_state.get("alerts", [])
                        if isinstance(alerts, list):
                            max_slot = max(
                                max_slot,
                                max((int(row.get("slotHour", 0)) for row in alerts if isinstance(row, dict)), default=0),
                            )
            migrated["days"][day_key] = {
                "suppressedThroughHour": max(EARLIEST_SCAN_HOUR - 1, min(LAST_SCAN_HOUR, max_slot)),
                "symbols": {base: {"alerts": []} for base in TARGET_BASES},
            }
        return migrated

    def _load_state(self) -> dict[str, Any]:
        state = load_json(str(self._state_path), self._empty_state())
        if not isinstance(state, dict):
            raise ValueError(f"Invalid H1 scanner state: {self._state_path}")
        if state.get("version") in {1, 2, 3, 4, 5, 6}:
            state = self._migrate_legacy_state(state)
            # Persist migration immediately so a restart cannot reload obsolete
            # pattern semantics and repeat the migration decision.
            self._save_state(state)
        if state.get("version") != STATE_VERSION or not isinstance(state.get("days"), dict):
            raise ValueError(f"Invalid H1 scanner state: {self._state_path}")
        for day_key, day_state in state["days"].items():
            if not isinstance(day_key, str) or not isinstance(day_state, dict):
                raise ValueError(f"Invalid H1 scanner day state: {self._state_path}")
            suppressed = day_state.get("suppressedThroughHour")
            if suppressed is not None and not isinstance(suppressed, int):
                raise ValueError(f"Invalid H1 scanner suppression state: {self._state_path}")
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

    def _publish_state_if_changed(self, state: dict[str, Any]) -> None:
        if self._publish_state is None:
            return
        import time

        now = time.time()
        if now < self._publish_retry_after:
            return
        signature = json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        if signature == self._last_published_signature:
            return
        try:
            self._publish_state(state, self._profile_name)
        except Exception as error:
            self._publish_retry_after = now + 300.0
            self._log_issue_once("h1-public-feed", f"[H1-SCAN] Public H1 feed publish lỗi: {error}", now_epoch=now)
            return
        self._publish_retry_after = 0.0
        self._last_published_signature = signature

    @staticmethod
    def _message(
        base: str,
        broker_symbol: str,
        scanner_base: str,
        scanner_symbol: str,
        match: H1PatternMatch,
        broker_day: str,
        base_context: H1BaseSignalContext,
        symbol_signal: str,
        profile_name: str,
    ) -> str:
        behavior = (
            f"giữ nguyên {base_context.base_symbol} H1"
            if pattern_follows_base(base, match.pattern_kind)
            else f"đảo {base_context.base_symbol} H1"
        )
        pattern_label = f"/!\\ {match.pattern_label}" if match.pattern_kind == PATTERN_KIND_SW3_PURE else match.pattern_label
        rows = [
            f"🔔 {base} H1 PATTERN",
            f"• Symbol: {broker_symbol}",
            f"• Profile: {profile_name}",
            f"• Ngày broker: {broker_day}",
            f"• Mốc scan: H{match.slot_hour:02d}",
            f"• Scanner pattern: {scanner_base} ({scanner_symbol})",
            f"• Nến xét nguồn (mới→cũ): {match.bar_range_text}",
            f"• Pattern nguồn: {match.pattern_text}",
            f"• Nhóm nguồn: {pattern_label}",
            base_context.telegram_line,
            f"• Logic nguồn: {behavior}",
        ]
        rows.append(f"• Signal {base} H1: {symbol_signal}")
        return "\n".join(rows)

    def scan_once(self) -> int:
        try:
            if not self._ensure_owner():
                return 0
            assert self._clock is not None
            broker_now = self._clock.now()

            try:
                state = self._load_state()
            except (JsonStateError, OSError, ValueError) as error:
                self._log_issue_once("state", f"[H1-SCAN] State lỗi, dừng alert để tránh replay: {error}")
                return 0

            if broker_now.hour < EARLIEST_SCAN_HOUR or broker_now.hour > LAST_SCAN_HOUR:
                self._publish_state_if_changed(state)
                return 0

            timeframe = getattr(self._mt5, "TIMEFRAME_H1", None)
            if timeframe is None:
                self._log_issue_once("timeframe", "[H1-SCAN] MT5 không có TIMEFRAME_H1.")
                return 0

            broker_symbols: dict[str, str] = {base: symbol for base, symbol in self._symbols.items() if base in REQUIRED_HISTORY_BASES}
            if self._gbpusd_symbol:
                broker_symbols["GBPUSD"] = self._gbpusd_symbol

            candles_by_base: dict[str, dict[int, tuple[datetime, str]]] = {}
            for base in REQUIRED_HISTORY_BASES:
                broker_symbol = broker_symbols.get(base)
                if not broker_symbol:
                    continue
                try:
                    rates = self._mt5.copy_rates_from_pos(broker_symbol, timeframe, 1, HISTORY_BARS)
                except Exception as error:
                    self._log_issue_once(f"rates:{base}", f"[H1-SCAN] Không lấy được H1 của {broker_symbol}: {error}")
                    continue
                if rates is None:
                    continue
                try:
                    candles_by_base[base] = closed_h1_directions_by_hour(
                        rates,
                        broker_now,
                        self._clock.broker_datetime_from_mt5_timestamp,
                    )
                except Exception as error:
                    self._log_issue_once(f"rates:{base}:decode", f"[H1-SCAN] Decode H1 {base} lỗi: {error}")

            source_matches = {
                base: _matches_from_candles(candles_by_base.get(base, {}), broker_now.hour)
                for base in SCANNER_BASES
            }

            day_key = broker_now.date().isoformat()
            day_state = state["days"].setdefault(day_key, {"symbols": {}})
            symbol_states = day_state.setdefault("symbols", {})
            suppressed_through = int(day_state.get("suppressedThroughHour") or 0)
            sent = 0

            for base in TARGET_BASES:
                broker_symbol = self._symbols.get(base)
                if not broker_symbol:
                    continue
                scanner_base = scanner_base_for_target(base)
                scanner_symbol = self._gbpusd_symbol if scanner_base == "GBPUSD" else self._symbols.get(scanner_base)
                base_symbol = base_symbol_for_target(base)
                base_candles = candles_by_base.get(base_symbol, {})
                matches = source_matches.get(scanner_base, [])

                symbol_state = symbol_states.setdefault(base, {"alerts": []})
                alerts = symbol_state.setdefault("alerts", [])
                delivered = {
                    int(row["slotHour"])
                    for row in alerts
                    if isinstance(row, dict) and isinstance(row.get("slotHour"), int)
                }
                for hour in range(EARLIEST_SCAN_HOUR, suppressed_through + 1):
                    delivered.add(hour)

                for match in matches:
                    if match.slot_hour in delivered:
                        continue
                    base_row = base_candles.get(match.slot_hour - 1)
                    if base_row is None:
                        self._log_issue_once(
                            f"base:{base}:{match.slot_hour}",
                            f"[H1-SCAN] {base} H{match.slot_hour:02d} chờ {base_symbol} H{match.slot_hour - 1:02d} đóng.",
                        )
                        break
                    opened, direction = base_row
                    base_context = H1BaseSignalContext(
                        base_symbol=base_symbol,
                        base_hour=opened.hour,
                        base_direction=direction,
                        signal=signal_from_h1_direction(direction),
                    )
                    symbol_signal = signal_from_pattern_base(base, base_context.signal, match.pattern_kind)
                    message = self._message(
                        base,
                        broker_symbol,
                        scanner_base,
                        scanner_symbol or scanner_base,
                        match,
                        day_key,
                        base_context,
                        symbol_signal,
                        self._profile_name,
                    )
                    if not bool(self._notify(message)):
                        self._log_issue_once(
                            f"telegram:{base}",
                            f"[H1-SCAN] {base} H{match.slot_hour:02d} đang chờ Telegram gửi thành công.",
                        )
                        self._publish_state_if_changed(state)
                        return sent

                    alerts.append({
                        "slotHour": match.slot_hour,
                        "pattern": match.pattern_text,
                        "patternKind": match.pattern_kind,
                        "bars": [value.isoformat(timespec="minutes") for value in match.bar_times],
                        "symbol": broker_symbol,
                        "profile": self._profile_name,
                        "scannerBase": scanner_base,
                        "scannerSymbol": scanner_symbol or scanner_base,
                        "baseSymbol": base_symbol,
                        "baseH1Signal": base_context.signal,
                        "baseHour": base_context.base_hour,
                        "baseDirection": base_context.base_direction or "",
                        "symbolH1Signal": symbol_signal,
                    })
                    alerts.sort(key=lambda item: int(item.get("slotHour", 0)))
                    delivered.add(match.slot_hour)
                    self._save_state(state)
                    self._publish_state_if_changed(state)
                    self._log(
                        f"[H1-SCAN] {base} H{match.slot_hour:02d} · scanner={scanner_base} · "
                        f"{match.pattern_kind} · base={base_symbol}:{base_context.signal} · signal={symbol_signal}"
                    )
                    sent += 1

            self._publish_state_if_changed(state)
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
        if owner_context is not None:
            try:
                owner_context.__exit__(None, None, None)
            except Exception:
                pass


XauH1PatternScanner = MultiSymbolH1PatternScanner
