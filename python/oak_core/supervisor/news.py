# -*- coding: utf-8 -*-
"""Read-only local economic-news cache for the Tauri shell.

The website dashboard shows the daily economic-news briefing; the desktop
shell had no equivalent.  The signal stack already writes the briefing to
``news_cache_VN.json`` / ``news_cache_EN.json`` next to the other local
artefacts, so this module projects those files into a sanitized, bounded
read model.

Read-only by construction: no network, no RSS/HTTP fetch, no Redis, no
website API key, no caller-supplied paths — the cache is never written or
refreshed from here.  A missing or corrupt cache degrades to an empty,
"unavailable" payload instead of raising, because a news panel must never
take the sidecar down.

Freshness is judged against the *broker* day stamped by the bot
(``bot_state.json``), using the same trust rule as ``history.py``: without a
verified stamp the answer is "unknown" (``stale = None``), never the
workstation date.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .profiles import _data_root

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: Hard ceiling for one news response (§ bounded IPC payloads).
MAX_ITEMS = 100
#: Longest headline echoed back — the cache is display data only.
_MAX_TITLE = 160
_MAX_CURRENCY = 6

_LOCALES = ("VN", "EN")

#: ``• 05:45 NZD 🔴 [HIGH] Employment Change q/q`` — bullet already stripped.
_LINE_RE = re.compile(r"^(\d{1,2}):(\d{2})\s+([A-Za-z]{2,6})\s+(\S.*)$")

#: ASCII impact tags written by ``oak_trading_reminders.format_news_line``.
_IMPACT_TAGS = (
    ("[NỔI BẬT]", "high"),
    ("[NOI BAT]", "high"),
    ("[HIGH]", "high"),
    ("[MEDIUM]", "medium"),
    ("[LOW]", "low"),
)
_IMPACT_ICONS = (("🔴", "high"), ("🟠", "medium"), ("🟡", "medium"), ("🟢", "low"))
_CRITICAL_TAGS = ("[NỔI BẬT]", "[NOI BAT]")

#: Events the desktop must not under-state; mirrors CRITICAL_NEWS_KEYWORDS.
_CRITICAL_KEYWORDS = (
    "federal funds rate",
    "fed interest rate decision",
    "federal fund rate",
    "interest rate decision",
    "fomc statement",
    "fomc press conference",
    "fomc economic projections",
    "non-farm payrolls",
    "nonfarm payrolls",
    "non farm payrolls",
)

#: Decoration removed from a headline before it is shown.
_NOISE_ICONS = ("🔴", "🟠", "🟡", "🟢", "⚠️")
_NOISE_TAG_RE = re.compile(r"\[(?:HIGH|MEDIUM|LOW|NỔI BẬT|NOI BAT)\]", re.IGNORECASE)


# ---------------------------------------------------------------------- #
# File access (never raises)
# ---------------------------------------------------------------------- #
def _read_json(path: Path, default: Any) -> Any:
    try:
        if not path.is_file():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _normalise_locale(locale: Any) -> str:
    value = str(locale or "").strip().upper()
    return value if value in _LOCALES else "VN"


def _cache_path(locale: str) -> Path:
    """Data root wins; the repo copy is the dev fallback."""
    name = f"news_cache_{locale}.json"
    local = _data_root() / name
    return local if local.is_file() else _REPO_ROOT / name


# ---------------------------------------------------------------------- #
# Line parsing / sanitisation
# ---------------------------------------------------------------------- #
def _classify(rest: str) -> tuple[str, bool]:
    """Impact bucket + critical flag from the decoration of one line.

    An unmarked line is treated as ``high``: the cache pipeline only keeps
    high-impact events, and under-stating an event is the unsafe direction.
    """
    upper = rest.upper()
    critical = any(tag in rest or tag in upper for tag in _CRITICAL_TAGS)
    for tag, impact in _IMPACT_TAGS:
        if tag in rest or tag in upper:
            return impact, critical
    for icon, impact in _IMPACT_ICONS:
        if icon in rest:
            return impact, critical
    return "high", critical


def _clean_title(rest: str) -> str:
    title = _NOISE_TAG_RE.sub("", rest)
    for icon in _NOISE_ICONS:
        title = title.replace(icon, "")
    return re.sub(r"\s+", " ", title).strip()[:_MAX_TITLE]


def _parse_line(raw: Any, cache_date: str | None) -> dict[str, Any] | None:
    """One sanitized news item, or ``None`` when the line is unusable."""
    if not isinstance(raw, str):
        return None
    line = re.sub(r"^[•\-–—\s]+", "", raw).strip()
    line = re.sub(r"^⚠️\s*", "", line).strip()
    match = _LINE_RE.match(line)
    if not match:
        return None
    hour, minute, currency, rest = match.groups()
    if int(hour) > 23 or int(minute) > 59:
        return None
    title = _clean_title(rest)
    if not title:
        return None
    impact, critical = _classify(rest)
    return {
        "date": cache_date,
        "time": f"{int(hour):02d}:{minute}",
        "currency": currency.upper()[:_MAX_CURRENCY],
        "title": title,
        "impact": impact,
        "critical": critical or any(kw in title.lower() for kw in _CRITICAL_KEYWORDS),
    }


def _cache_date(value: Any) -> str | None:
    text = str(value or "").strip()[:32]
    return text or None


def _cache_version(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


# ---------------------------------------------------------------------- #
# Broker day (never the workstation clock)
# ---------------------------------------------------------------------- #
def _verified_broker_date() -> tuple[str | None, bool]:
    """``(broker_date, verified)`` from bot_state.json — same rule as history.

    ``mt5_signal_bot.save_state`` writes ``broker_time``/``broker_utc_offset``
    only when the broker clock was verified, so an empty stamp or a missing
    offset means "clock not trusted".  An unverified stamp yields no date at
    all: the desktop must never present workstation time as a broker day.
    """
    state = _read_json(_data_root() / "bot_state.json", {})
    if not isinstance(state, dict):
        return None, False
    stamp = str(state.get("broker_time") or "")
    offset = state.get("broker_utc_offset")
    has_offset = isinstance(offset, (int, float)) and not isinstance(offset, bool)
    if not stamp or not has_offset:
        return None, False
    date_part, _, _time_part = stamp.partition("T")
    broker_date = (str(state.get("date") or "") or date_part) or None
    return broker_date, broker_date is not None


# ---------------------------------------------------------------------- #
# Public read model
# ---------------------------------------------------------------------- #
def local_news(locale: Any = "VN") -> dict[str, Any]:
    """Sanitized local economic-news cache for ``locale`` (max ``MAX_ITEMS``)."""
    selected = _normalise_locale(locale)
    warnings: list[str] = []

    envelope = _read_json(_cache_path(selected), None)
    available = isinstance(envelope, dict)
    if not available:
        envelope = {}
        warnings.append("news_cache_unavailable")

    cache_date = _cache_date(envelope.get("date"))
    lines = envelope.get("news")
    if available and not isinstance(lines, list):
        warnings.append("news_cache_malformed")
        lines = []

    items: list[dict[str, Any]] = []
    dropped = 0
    truncated = False
    for raw in lines if isinstance(lines, list) else []:
        if len(items) >= MAX_ITEMS:
            truncated = True
            break
        item = _parse_line(raw, cache_date)
        if item is None:
            dropped += 1
            continue
        items.append(item)

    if dropped:
        warnings.append("malformed_lines_dropped")
    if truncated:
        warnings.append("item_limit_reached")
    if available and not items and "news_cache_malformed" not in warnings:
        warnings.append("news_cache_empty")

    broker_date, verified = _verified_broker_date()
    if not verified:
        stale: bool | None = None
        warnings.append("broker_clock_unverified")
    elif cache_date is None:
        stale = None
        warnings.append("cache_date_unknown")
    else:
        stale = cache_date != broker_date

    return {
        "available": available,
        "source": "local_news_cache",
        "locale": selected,
        "cache_date": cache_date,
        "cache_version": _cache_version(envelope.get("v")),
        "broker_date": broker_date,
        "broker_clock_verified": verified,
        "stale": stale,
        "warnings": warnings,
        "items": items,
        "count": len(items),
    }
