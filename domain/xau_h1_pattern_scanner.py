# -*- coding: utf-8 -*-
"""Passive multi-symbol H1 pattern scanner with Telegram delivery state.

The scanner is independent from Engine5's active-symbol scope. Exactly one
MonitorWorker owns it across profile worker processes. The legacy XAU state and
lock paths are intentionally retained for rolling compatibility and replay
protection.
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

PURE_SW_3_PATTERNS = {("T", "G", "G"), ("G", "T", "T")}
TWO_CANDLE_SW_PATTERNS = {("T", "G"), ("G", "T")}
ALTERNATING_SW_3_PATTERNS = {("T", "G", "T"), ("G", "T", "G")}
ALTERNATING_SW_4_PATTERNS = {("T", "G", "T", "G"), ("G", "T", "G", "T")}

PATTERN_KIND_SW2 = "sw2"
PATTERN_KIND_SW3_PURE = "sw3Pure"
PATTERN_KIND_SW3_ALTERNATING = "sw3Alternating"
PATTERN_KIND_SW6_COMBINED = "sw6CombinedPure"
PATTERN_KINDS = {
    PATTERN_KIND_SW2,
    PATTERN_KIND_SW3_PURE,
    PATTERN_KIND_SW3_ALTERNATING,
    PATTERN_KIND_SW6_COMBINED,
}
PATTERN_LABELS = {
    PATTERN_KIND_SW2: "SW 2 cây",
    PATTERN_KIND_SW3_PURE: "SW 3 cây thuần",
    PATTERN_KIND_SW3_ALTERNATING: "SW 3 cây xen kẽ",
    PATTERN_KIND_SW6_COMBINED: "SW ghép 2×3 cây thuần",
}
REVERSE_TARGET_PATTERN_KINDS = {
    PATTERN_KIND_SW2,
    PATTERN_KIND_SW3_ALTERNATING,
    PATTERN_KIND_SW6_COMBINED,
}
FOLLOW_TARGET_PATTERN_KINDS = {PATTERN_KIND_SW3_PURE}

XAU_FIRST_SCAN_HOUR = 4
FX_FIRST_SCAN_HOUR = 3
EARLIEST_SCAN_HOUR = min(XAU_FIRST_SCAN_HOUR, FX_FIRST_SCAN_HOUR)
LAST_SCAN_HOUR = 17
HISTORY_BARS = 32
STATE_VERSION = 2


@dataclass(frozen=True, slots=True)
class H1PatternMatch:
    slot_hour: int
    pattern: tuple[str, ...]
    bar_times: tuple[datetime, ...]
    pattern_kind: str = PATTERN_KIND_SW3_PURE

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
class GbpUsdH1SignalContext:
    base_hour: int
    base_direction: str | None
    signal: str | None
    unavailable_reason: str = ""

    @property
    def telegram_line(self) -> str:
        if self.signal and self.base_direction:
            return f"• Signal GBPUSD H1: {self.signal} | Base H{self.base_hour:02d}={self.base_direction}"
        reason = self.unavailable_reason or "chưa đủ dữ liệu"
        return f"• Signal GBPUSD H1: N/A | Base H{self.base_hour:02d} ({reason})"


def signal_from_h1_direction(direction: str) -> str:
    canonical = str(direction or "").strip().upper()
    if canonical == "T":
        return "BUY"
    if canonical == "G":
        return "SELL"
    raise ValueError(f"Unknown H1 direction: {direction}")


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


def _rows_for_hours(
    candles: dict[int, tuple[datetime, str]],
    hours: tuple[int, ...],
) -> list[tuple[datetime, str]] | None:
    selected = [candles.get(hour) for hour in hours]
    if any(item is None for item in selected):
        return None
    return [item for item in selected if item is not None]


def find_h1_pattern_matches(
    rates: Iterable[Any],
    broker_now: datetime,
    decode_time: Callable[[int], datetime],
    first_scan_hour: int = XAU_FIRST_SCAN_HOUR,
) -> list[H1PatternMatch]:
    """Find the four supported H1 pattern classes newest→oldest.

    First slot matches TG/GT. Later slots match TGG/GTT, exact TGT/GTG (but
    reject TGTG/GTGT), or six candles made from two non-overlapping TGG/GTT
    groups. Combined-six has precedence over its embedded latest-three match.
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
            rows = _rows_for_hours(candles, (slot_hour - 1, slot_hour - 2))
            if not rows:
                continue
            pattern = tuple(direction for _opened, direction in rows)
            if pattern in TWO_CANDLE_SW_PATTERNS:
                matches.append(H1PatternMatch(
                    slot_hour,
                    pattern,
                    tuple(opened for opened, _direction in rows),
                    PATTERN_KIND_SW2,
                ))
            continue

        # H08 for XAU and H07 for FX are the earliest six-candle slots.
        if slot_hour >= first_scan_hour + 4:
            six_hours = tuple(slot_hour - offset for offset in range(1, 7))
            six_rows = _rows_for_hours(candles, six_hours)
            if six_rows:
                six_pattern = tuple(direction for _opened, direction in six_rows)
                if six_pattern[:3] in PURE_SW_3_PATTERNS and six_pattern[3:] in PURE_SW_3_PATTERNS:
                    matches.append(H1PatternMatch(
                        slot_hour,
                        six_pattern,
                        tuple(opened for opened, _direction in six_rows),
                        PATTERN_KIND_SW6_COMBINED,
                    ))
                    continue

        rows = _rows_for_hours(candles, (slot_hour - 1, slot_hour - 2, slot_hour - 3))
        if not rows:
            continue
        pattern = tuple(direction for _opened, direction in rows)
        if pattern in PURE_SW_3_PATTERNS:
            matches.append(H1PatternMatch(
                slot_hour,
                pattern,
                tuple(opened for opened, _direction in rows),
                PATTERN_KIND_SW3_PURE,
            ))
            continue
        if pattern not in ALTERNATING_SW_3_PATTERNS:
            continue

        older = candles.get(slot_hour - 4)
        if older is not None and (*pattern, older[1]) in ALTERNATING_SW_4_PATTERNS:
            continue
        matches.append(H1PatternMatch(
            slot_hour,
            pattern,
            tuple(opened for opened, _direction in rows),
            PATTERN_KIND_SW3_ALTERNATING,
        ))
    return matches


def pattern_kind_from_text(pattern_text: str) -> str | None:
    pattern = tuple(str(pattern_text or "").strip().upper().split())
    if pattern in TWO_CANDLE_SW_PATTERNS:
        return PATTERN_KIND_SW2
    if pattern in PURE_SW_3_PATTERNS:
        return PATTERN_KIND_SW3_PURE
    if pattern in ALTERNATING_SW_3_PATTERNS:
        return PATTERN_KIND_SW3_ALTERNATING
    if len(pattern) == 6 and pattern[:3] in PURE_SW_3_PATTERNS and pattern[3:] in PURE_SW_3_PATTERNS:
        return PATTERN_KIND_SW6_COMBINED
    return None


def signal_from_gbpusd_pattern(gbpusd_signal: str, pattern_kind: str) -> str:
    """Derive target H1 signal solely from GBPUSD H1 + matched pattern class."""
    signal = str(gbpusd_signal or "").strip().upper()
    if signal not in {"BUY", "SELL"}:
        raise ValueError("GBPUSD H1 signal must be BUY or SELL")
    if pattern_kind in FOLLOW_TARGET_PATTERN_KINDS:
        return signal
    if pattern_kind in REVERSE_TARGET_PATTERN_KINDS:
        return "SELL" if signal == "BUY" else "BUY"
    raise ValueError(f"Unknown H1 pattern kind: {pattern_kind}")


class MultiSymbolH1PatternScanner:
    """One-owner H1 scanner using only current-day H1 charts."""

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
            self._log_issue_once("GBPUSD", "[H1-SCAN] Không tìm thấy GBPUSD hoặc biến thể hậu tố.")

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
        self._log(
            f"[H1-SCAN] Scanner owner={self._profile_name} · {rendered} · GBPUSD-ref={gbpusd_symbol or 'N/A'} · "
            "H1 current-day only · XAU H04-H17; FX H03-H17 · "
            "patterns=SW2, SW3-pure, SW3-alternating, SW6-combined"
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

    @staticmethod
    def _normalize_legacy_state(state: dict[str, Any]) -> bool:
        changed = False
        for day_state in state.get("days", {}).values():
            if not isinstance(day_state, dict):
                continue
            symbols = day_state.get("symbols", {})
            if not isinstance(symbols, dict):
                continue
            for symbol_state in symbols.values():
                if not isinstance(symbol_state, dict):
                    continue
                for key in ("dayType", "firstSignalHour", "symbolH1Signal", "gbpusdH1Signal"):
                    if key in symbol_state:
                        symbol_state.pop(key, None)
                        changed = True
                alerts = symbol_state.get("alerts", [])
                if not isinstance(alerts, list):
                    continue
                for alert in alerts:
                    if not isinstance(alert, dict):
                        continue
                    for key in ("dayType", "entryTime", "gbpusdBlockHour", "gbpusdGroup"):
                        if key in alert:
                            alert.pop(key, None)
                            changed = True
                    kind = str(alert.get("patternKind") or "").strip()
                    if kind not in PATTERN_KINDS:
                        kind = pattern_kind_from_text(str(alert.get("pattern") or "")) or ""
                        if kind:
                            alert["patternKind"] = kind
                            changed = True
                    gbp_signal = str(alert.get("gbpusdH1Signal") or "").strip().upper()
                    if kind in PATTERN_KINDS and gbp_signal in {"BUY", "SELL"}:
                        target_signal = signal_from_gbpusd_pattern(gbp_signal, kind)
                        if alert.get("symbolH1Signal") != target_signal:
                            alert["symbolH1Signal"] = target_signal
                            changed = True
        return changed

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

    def _gbpusd_signal_context(
        self,
        slot_hour: int,
        gbp_candles: dict[int, tuple[datetime, str]],
    ) -> GbpUsdH1SignalContext:
        base_hour = int(slot_hour) - 1
        if not self._gbpusd_symbol:
            return GbpUsdH1SignalContext(base_hour, None, None, "không có GBPUSD broker")
        base_row = gbp_candles.get(base_hour)
        if base_row is None:
            return GbpUsdH1SignalContext(base_hour, None, None, f"thiếu GBPUSD H{base_hour:02d} đã đóng")
        _opened, direction = base_row
        return GbpUsdH1SignalContext(base_hour, direction, signal_from_h1_direction(direction))

    def _message(
        self,
        base: str,
        broker_symbol: str,
        match: H1PatternMatch,
        broker_day: str,
        symbol_signal: str,
        gbpusd_signal: GbpUsdH1SignalContext,
    ) -> str:
        behavior = "giữ nguyên GBPUSD H1" if match.pattern_kind in FOLLOW_TARGET_PATTERN_KINDS else "đảo GBPUSD H1"
        return (
            f"🔔 {base} H1 PATTERN\n"
            f"• Symbol: {broker_symbol}\n"
            f"• Profile: {self._profile_name}\n"
            f"• Ngày broker: {broker_day}\n"
            f"• Mốc scan: H{match.slot_hour:02d}\n"
            f"• Nến xét (mới→cũ): {match.bar_range_text}\n"
            f"• Pattern: {match.pattern_text}\n"
            f"• Nhóm pattern: {match.pattern_label}\n"
            f"{gbpusd_signal.telegram_line}\n"
            f"• Logic Signal {base}: {behavior}\n"
            f"• Signal {base} H1: {symbol_signal}"
        )

    def _enrich_existing_alerts(
        self,
        alerts: list[dict[str, Any]],
        current_matches: dict[int, H1PatternMatch],
        gbp_candles: dict[int, tuple[datetime, str]],
    ) -> bool:
        """Backfill current H1-only fields without replaying delivered Telegram alerts."""
        changed = False
        for alert in alerts:
            if not isinstance(alert, dict) or not isinstance(alert.get("slotHour"), int):
                continue
            slot_hour = int(alert["slotHour"])
            for key in ("dayType", "entryTime", "gbpusdBlockHour", "gbpusdGroup"):
                if key in alert:
                    alert.pop(key, None)
                    changed = True

            current = current_matches.get(slot_hour)
            if current is not None:
                canonical_pattern = current.pattern_text
                canonical_bars = [value.isoformat(timespec="minutes") for value in current.bar_times]
                if alert.get("pattern") != canonical_pattern:
                    alert["pattern"] = canonical_pattern
                    changed = True
                if alert.get("bars") != canonical_bars:
                    alert["bars"] = canonical_bars
                    changed = True
                if alert.get("patternKind") != current.pattern_kind:
                    alert["patternKind"] = current.pattern_kind
                    changed = True

            pattern_kind = str(alert.get("patternKind") or "").strip()
            if pattern_kind not in PATTERN_KINDS:
                pattern_kind = pattern_kind_from_text(str(alert.get("pattern") or "")) or ""
                if pattern_kind:
                    alert["patternKind"] = pattern_kind
                    changed = True
            if pattern_kind not in PATTERN_KINDS:
                continue

            gbp_context = self._gbpusd_signal_context(slot_hour, gbp_candles)
            if not gbp_context.signal:
                continue
            canonical = {
                "symbolH1Signal": signal_from_gbpusd_pattern(gbp_context.signal, pattern_kind),
                "gbpusdH1Signal": gbp_context.signal,
                "gbpusdBaseHour": gbp_context.base_hour,
                "gbpusdBaseDirection": gbp_context.base_direction or "",
            }
            for key, value in canonical.items():
                if alert.get(key) != value:
                    alert[key] = value
                    changed = True
        alerts.sort(key=lambda item: int(item.get("slotHour", 0)))
        return changed

    def scan_once(self) -> int:
        """Scan current broker day across target symbols; return Telegram sends."""
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
            if self._normalize_legacy_state(state):
                self._save_state(state)

            if broker_now.hour < EARLIEST_SCAN_HOUR or broker_now.hour > LAST_SCAN_HOUR:
                self._publish_state_if_changed(state)
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
                first_scan_hour = XAU_FIRST_SCAN_HOUR if base == "XAUUSD" else FX_FIRST_SCAN_HOUR
                if broker_now.hour < first_scan_hour:
                    continue

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

                matches = find_h1_pattern_matches(
                    rates,
                    broker_now,
                    self._clock.broker_datetime_from_mt5_timestamp,
                    first_scan_hour=first_scan_hour,
                )
                by_slot = {match.slot_hour: match for match in matches}
                if self._enrich_existing_alerts(alerts, by_slot, gbp_candles):
                    self._save_state(state)
                    self._publish_state_if_changed(state)

                delivered_slots = {
                    int(item["slotHour"])
                    for item in alerts
                    if isinstance(item, dict) and isinstance(item.get("slotHour"), int)
                }
                pending = [match for match in matches if match.slot_hour not in delivered_slots]
                for match in pending:
                    gbpusd_signal = self._gbpusd_signal_context(match.slot_hour, gbp_candles)
                    if not gbpusd_signal.signal:
                        self._log_issue_once(
                            f"gbp-signal:{base}:{match.slot_hour}",
                            f"[H1-SCAN] {base} match H{match.slot_hour:02d} đang chờ GBPUSD H{match.slot_hour - 1:02d} đóng.",
                        )
                        break

                    symbol_signal = signal_from_gbpusd_pattern(gbpusd_signal.signal, match.pattern_kind)
                    if not bool(self._notify(self._message(
                        base,
                        broker_symbol,
                        match,
                        day_key,
                        symbol_signal,
                        gbpusd_signal,
                    ))):
                        self._log_issue_once(
                            f"telegram:{base}",
                            f"[H1-SCAN] {base} match H{match.slot_hour:02d} đang chờ Telegram gửi thành công.",
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
                        "symbolH1Signal": symbol_signal,
                        "gbpusdH1Signal": gbpusd_signal.signal,
                        "gbpusdBaseHour": gbpusd_signal.base_hour,
                        "gbpusdBaseDirection": gbpusd_signal.base_direction or "",
                    })
                    alerts.sort(key=lambda item: int(item.get("slotHour", 0)))
                    self._save_state(state)
                    self._publish_state_if_changed(state)
                    self._log(
                        f"[H1-SCAN] {base} đã gửi H{match.slot_hour:02d} {match.pattern_text} · "
                        f"{match.pattern_kind} · GBPUSD={gbpusd_signal.signal} · target={symbol_signal}"
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
