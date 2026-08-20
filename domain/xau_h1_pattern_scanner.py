# -*- coding: utf-8 -*-
"""Passive XAUUSD H1 pattern scanner with Telegram delivery state.

This scanner is intentionally independent from Engine5's active-symbol scope.
Exactly one MonitorWorker owns the scanner at a time across all profile worker
processes. Ownership is an OS-backed FileLock, while alert state is persisted so
worker/process restarts do not replay already delivered intraday matches.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from domain.broker_clock import BrokerClock, BrokerClockError
from domain.file_lock import FileLock
from domain.json_io import JsonStateError, load_json, save_json

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STATE_PATH = ROOT / "xau_h1_pattern_alert_state.json"
DEFAULT_OWNER_LOCK_PATH = ROOT / "xau_h1_pattern_scanner.lock"
TARGET_PREFIX = "XAUUSD"
TARGET_PATTERNS = {("T", "G", "G"), ("G", "T", "T")}
H4_TARGET_PATTERNS = {("T", "G"), ("G", "T")}
FIRST_SCAN_HOUR = 4
LAST_SCAN_HOUR = 17
MAX_ALERTS_PER_DAY = 2
HISTORY_BARS = 32


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


def resolve_xauusd_symbol(symbols: Iterable[Any]) -> str | None:
    """Resolve XAUUSD, accepting arbitrary broker suffixes but no prefixes."""
    candidates: list[tuple[int, int, str]] = []
    for item in symbols:
        name = str(getattr(item, "name", item) or "").strip()
        upper = name.upper()
        if not upper.startswith(TARGET_PREFIX):
            continue
        exact_rank = 0 if upper == TARGET_PREFIX else 1
        visible_rank = 0 if bool(getattr(item, "visible", False)) else 1
        candidates.append((visible_rank, exact_rank, name))
    if not candidates:
        return None
    candidates.sort(key=lambda row: (row[0], row[1], len(row[2]), row[2].upper()))
    return candidates[0][2]


def _rate_value(rate: Any, key: str) -> Any:
    try:
        return rate[key]
    except (KeyError, IndexError, TypeError):
        return getattr(rate, key)


def find_h1_pattern_matches(
    rates: Iterable[Any],
    broker_now: datetime,
    decode_time: Callable[[int], datetime],
) -> list[H1PatternMatch]:
    """Return eligible backward-looking H1 matches from the current broker day.

    H04 is special: H01 is treated as noise, so only H03→H02 is inspected and
    must be TG or GT. From H05 through H17, each scan slot inspects the three
    most recent fully closed H1 candles in backward order (newest→oldest).
    """
    if broker_now.tzinfo is not None:
        raise ValueError("broker_now must be a naive broker-wall datetime")
    if broker_now.hour < FIRST_SCAN_HOUR or broker_now.hour > LAST_SCAN_HOUR:
        return []

    current_hour = broker_now.replace(minute=0, second=0, microsecond=0)
    candles: dict[int, tuple[datetime, str]] = {}
    for rate in rates:
        opened = decode_time(int(_rate_value(rate, "time")))
        if opened.tzinfo is not None:
            raise ValueError("decoded MT5 candle time must be naive broker wall time")
        if opened.date() != broker_now.date():
            continue
        if opened >= current_hour:
            continue  # never inspect the currently forming H1 candle
        if opened.minute or opened.second or opened.microsecond:
            continue
        direction = "T" if float(_rate_value(rate, "close")) > float(_rate_value(rate, "open")) else "G"
        candles[opened.hour] = (opened, direction)

    matches: list[H1PatternMatch] = []
    for slot_hour in range(FIRST_SCAN_HOUR, min(broker_now.hour, LAST_SCAN_HOUR) + 1):
        lookback_hours = (3, 2) if slot_hour == FIRST_SCAN_HOUR else (slot_hour - 1, slot_hour - 2, slot_hour - 3)
        selected = [candles.get(hour) for hour in lookback_hours]
        if any(item is None for item in selected):
            continue
        rows = [item for item in selected if item is not None]
        pattern = tuple(direction for _opened, direction in rows)
        expected = H4_TARGET_PATTERNS if slot_hour == FIRST_SCAN_HOUR else TARGET_PATTERNS
        if pattern not in expected:
            continue
        matches.append(H1PatternMatch(slot_hour, pattern, tuple(opened for opened, _direction in rows)))
    return matches


class XauH1PatternScanner:
    """One-owner rolling H1 scanner that sends at most two alerts per broker day."""

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
    ) -> None:
        self._mt5 = mt5_module
        self._notify = notify
        self._log = log or (lambda _message: None)
        self._profile_name = str(profile_name or "unknown")
        self._state_path = Path(state_path)
        self._owner_lock_path = Path(owner_lock_path)
        self._clock_factory = clock_factory
        self._lock_factory = lock_factory
        self._owner_context: Any | None = None
        self._owner_guard: Any | None = None
        self._clock: Any | None = None
        self._symbol: str | None = None
        self._issue_last_logged: dict[str, float] = {}

    @property
    def is_owner(self) -> bool:
        return self._owner_guard is not None

    @property
    def symbol(self) -> str | None:
        return self._symbol

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
            symbols = self._mt5.symbols_get() or []
        except Exception as error:
            self._log_issue_once("symbols", f"[XAU-H1] Không đọc được danh sách symbol: {error}")
            return False
        symbol = resolve_xauusd_symbol(symbols)
        if not symbol:
            self._log_issue_once("symbol", "[XAU-H1] Không tìm thấy XAUUSD hoặc biến thể có hậu tố trên terminal này.")
            return False
        try:
            if self._mt5.symbol_select(symbol, True) is False:
                self._log_issue_once("select", f"[XAU-H1] Không select được {symbol}.")
                return False
        except Exception as error:
            self._log_issue_once("select", f"[XAU-H1] Không select được {symbol}: {error}")
            return False

        owner_context = self._lock_factory(str(self._owner_lock_path), timeout=0.0)
        owner_guard = owner_context.__enter__()
        if owner_guard is None:
            return False
        try:
            clock = self._clock_factory(
                mt5_module=self._mt5,
                symbols=(symbol,),
                cache_path=str(ROOT / "broker_clock_cache.json"),
            )
        except Exception:
            owner_context.__exit__(None, None, None)
            raise
        self._owner_context = owner_context
        self._owner_guard = owner_guard
        self._clock = clock
        self._symbol = symbol
        self._log(f"[XAU-H1] Scanner owner={self._profile_name} symbol={symbol} · H04-H17 · H04=TG/GT, H05+=TGG/GTT · max 2 alerts/day")
        return True

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        return {"version": 1, "days": {}}

    def _load_state(self) -> dict[str, Any]:
        state = load_json(str(self._state_path), self._empty_state())
        if not isinstance(state, dict) or state.get("version") != 1 or not isinstance(state.get("days"), dict):
            raise ValueError(f"Invalid XAU H1 scanner state: {self._state_path}")
        for day_key, day_state in state["days"].items():
            if not isinstance(day_key, str) or not isinstance(day_state, dict):
                raise ValueError(f"Invalid XAU H1 scanner day state: {self._state_path}")
            alerts = day_state.get("alerts", [])
            if not isinstance(alerts, list) or len(alerts) > MAX_ALERTS_PER_DAY:
                raise ValueError(f"Invalid XAU H1 scanner alerts: {self._state_path}")
            for alert in alerts:
                if not isinstance(alert, dict) or not isinstance(alert.get("slotHour"), int):
                    raise ValueError(f"Invalid XAU H1 scanner alert row: {self._state_path}")
        return state

    def _save_state(self, state: dict[str, Any]) -> None:
        days = state.get("days", {})
        if isinstance(days, dict) and len(days) > 14:
            keep = set(sorted(days)[-14:])
            state["days"] = {key: value for key, value in days.items() if key in keep}
        save_json(str(self._state_path), state)

    def _message(self, match: H1PatternMatch, alert_number: int, broker_day: str) -> str:
        return (
            f"🔔 XAU H1 PATTERN {alert_number}/{MAX_ALERTS_PER_DAY}\n"
            f"• Symbol: {self._symbol}\n"
            f"• Profile: {self._profile_name}\n"
            f"• Ngày broker: {broker_day}\n"
            f"• Mốc scan: H{match.slot_hour:02d}\n"
            f"• Nến xét (mới→cũ): {match.bar_range_text}\n"
            f"• Pattern: {match.pattern_text}"
        )

    def scan_once(self) -> int:
        """Scan current broker day and return the number of Telegram alerts sent."""
        try:
            if not self._ensure_owner():
                return 0
            assert self._clock is not None and self._symbol is not None
            broker_now = self._clock.now()
            if broker_now.hour < FIRST_SCAN_HOUR or broker_now.hour > LAST_SCAN_HOUR:
                return 0

            try:
                state = self._load_state()
            except (JsonStateError, OSError, ValueError) as error:
                self._log_issue_once("state", f"[XAU-H1] State lỗi, dừng alert để tránh replay: {error}")
                return 0

            day_key = broker_now.date().isoformat()
            day_state = state["days"].setdefault(day_key, {"alerts": []})
            alerts = day_state.setdefault("alerts", [])
            if len(alerts) >= MAX_ALERTS_PER_DAY:
                return 0

            timeframe = getattr(self._mt5, "TIMEFRAME_H1", None)
            if timeframe is None:
                self._log_issue_once("timeframe", "[XAU-H1] MT5 không có TIMEFRAME_H1.")
                return 0
            rates = self._mt5.copy_rates_from_pos(self._symbol, timeframe, 1, HISTORY_BARS)
            if rates is None:
                self._log_issue_once("rates", f"[XAU-H1] Không lấy được H1 đã đóng của {self._symbol}.")
                return 0

            matches = find_h1_pattern_matches(
                rates,
                broker_now,
                self._clock.broker_datetime_from_mt5_timestamp,
            )
            last_slot = max((int(item["slotHour"]) for item in alerts), default=FIRST_SCAN_HOUR - 1)
            pending = [match for match in matches if match.slot_hour > last_slot]
            sent = 0
            for match in pending:
                if len(alerts) >= MAX_ALERTS_PER_DAY:
                    break
                alert_number = len(alerts) + 1
                message = self._message(match, alert_number, day_key)
                if not bool(self._notify(message)):
                    self._log_issue_once("telegram", f"[XAU-H1] Match H{match.slot_hour:02d} đang chờ Telegram gửi thành công.")
                    break
                record = {
                    "slotHour": match.slot_hour,
                    "pattern": match.pattern_text,
                    "bars": [value.isoformat(timespec="minutes") for value in match.bar_times],
                    "symbol": self._symbol,
                    "profile": self._profile_name,
                }
                alerts.append(record)
                self._save_state(state)
                self._log(f"[XAU-H1] Đã gửi alert {alert_number}/{MAX_ALERTS_PER_DAY}: H{match.slot_hour:02d} {match.pattern_text}")
                sent += 1
                last_slot = match.slot_hour
            return sent
        except BrokerClockError as error:
            self._log_issue_once("clock", f"[XAU-H1] Chưa xác định được giờ broker an toàn: {error}")
            return 0
        except Exception as error:
            self._log_issue_once("scan", f"[XAU-H1] Scan lỗi: {error}")
            return 0

    def close(self) -> None:
        owner_context = self._owner_context
        self._owner_context = None
        self._owner_guard = None
        self._clock = None
        self._symbol = None
        if owner_context is not None:
            try:
                owner_context.__exit__(None, None, None)
            except Exception:
                pass
