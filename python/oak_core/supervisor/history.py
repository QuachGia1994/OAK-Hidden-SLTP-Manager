# -*- coding: utf-8 -*-
"""Read-only signal history + broker-day rule contract for the Tauri shell.

The website exposes a verified trade history and the published rule contract;
the desktop shell has neither.  oak-core is the canonical *local* source for
both, so these helpers read the on-disk artefacts written by the signal bot
(``signals_log.json``, ``bot_state.json``, ``signal_rule_contract.json``) and
project a sanitized, bounded view of them.

Read-only by construction: no MT5 connection, no network, no Redis, no
website API key, no SQLite, no caller-supplied paths.  Missing or malformed
files degrade to an empty/unavailable payload instead of raising, because a
history panel must never take the sidecar down.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .profiles import _data_root

_REPO_ROOT = Path(__file__).resolve().parents[3]

#: Hard ceiling for one history response (§ bounded IPC payloads).
MAX_RECORDS = 500
DEFAULT_LIMIT = 200

#: Longest string echoed back per field — the archive is display data only.
_MAX_TEXT = 240
#: Pair maps hold five symbols; the bound only guards a corrupted file.
_MAX_PAIRS = 16

#: Public scalar fields of one archived signal record.  Everything else
#: (``pair_evidence``, prices, internal notes, unknown future keys) is dropped.
_SCALAR_FIELDS = (
    "date",
    "hour",
    "signal",
    "signal_time",
    "entry_time",
    "entry_state",
    "signal_state",
    "signal_at_utc",
    "broker_utc_offset",
    "broker_clock_verified",
    "logic_version",
    "failure_reason",
)

#: Public per-pair maps of one archived signal record.
_MAP_FIELDS = ("pair_dirs", "pair_labels", "pair_entry_states")

_LOCALES = ("VN", "EN")

#: Parsed archive cache keyed by (path, mtime_ns, size).  signals_log.json is
#: multi-megabyte and the UI polls it, while the IPC loop is single threaded —
#: re-parsing an unchanged file would stall unrelated requests for ~0.2s.
_archive_cache: tuple[tuple[str, int, int], list[dict[str, Any]]] | None = None


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


def _signals_log_path() -> Path:
    return _data_root() / "signals_log.json"


def _rule_contract_path() -> Path:
    """Data root wins; the repo copy is the dev fallback."""
    local = _data_root() / "signal_rule_contract.json"
    return local if local.is_file() else _REPO_ROOT / "signal_rule_contract.json"


# ---------------------------------------------------------------------- #
# Sanitisation helpers
# ---------------------------------------------------------------------- #
def _scalar(value: Any) -> Any:
    """Keep JSON scalars only; truncate text; drop everything structured."""
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value[:_MAX_TEXT]
    return None


def _string_map(value: Any) -> dict[str, Any]:
    """Bounded {symbol: scalar} projection of a per-pair map."""
    if not isinstance(value, dict):
        return {}
    out: dict[str, Any] = {}
    for key, item in value.items():
        if len(out) >= _MAX_PAIRS:
            break
        out[str(key)[:_MAX_TEXT]] = _scalar(item)
    return out


def _public_record(record: dict) -> dict[str, Any]:
    out: dict[str, Any] = {key: _scalar(record.get(key)) for key in _SCALAR_FIELDS}
    for key in _MAP_FIELDS:
        out[key] = _string_map(record.get(key))
    return out


def _order_key(index: int, record: dict) -> tuple[str, float, int]:
    """Sort archived records by broker day, then slot hour, then file order."""
    hour = record.get("hour")
    numeric_hour = float(hour) if isinstance(hour, (int, float)) and not isinstance(hour, bool) else -1.0
    return (str(record.get("date") or ""), numeric_hour, index)


def _bounded_limit(limit: Any) -> int:
    try:
        value = int(limit)
    except (TypeError, ValueError):
        value = DEFAULT_LIMIT
    return max(1, min(value, MAX_RECORDS))


def _archive() -> list[dict[str, Any]]:
    """Sanitized archive, newest first, bounded to ``MAX_RECORDS``."""
    global _archive_cache
    path = _signals_log_path()
    try:
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
    except OSError:
        key = None
    if key is not None and _archive_cache is not None and _archive_cache[0] == key:
        return _archive_cache[1]

    raw = _read_json(path, [])
    if not isinstance(raw, list):
        raw = []
    ordered = sorted(
        ((index, item) for index, item in enumerate(raw) if isinstance(item, dict)),
        key=lambda pair: _order_key(pair[0], pair[1]),
        reverse=True,
    )
    records = [_public_record(item) for _index, item in ordered[:MAX_RECORDS]]
    _archive_cache = (key, records) if key is not None else None
    return records


# ---------------------------------------------------------------------- #
# Public read models
# ---------------------------------------------------------------------- #
def signal_history(limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
    """Sanitized local signal archive, newest first (max ``MAX_RECORDS``)."""
    records = _archive()[:_bounded_limit(limit)]
    return {"records": records, "source": "local_signal_log", "count": len(records)}


def _normalise_locale(locale: Any) -> str:
    value = str(locale or "").strip().upper()
    return value if value in _LOCALES else "VN"


def _rule_strings(rules: Any, locale: str) -> list[str]:
    if not isinstance(rules, dict):
        return []
    selected = rules.get(locale)
    if not isinstance(selected, list):
        return []
    return [item[:_MAX_TEXT * 4] for item in selected if isinstance(item, str)]


def _public_slots(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    return [int(item) for item in value if isinstance(item, int) and not isinstance(item, bool)]


def _broker_state() -> dict[str, Any]:
    """Broker-day metadata from bot_state.json — never from workstation time.

    ``mt5_signal_bot.save_state`` writes ``broker_time``/``broker_observed_at_utc``
    only when the broker clock was verified, so an empty stamp or a missing
    offset means "clock not trusted", not "clock is local time".
    """
    state = _read_json(_data_root() / "bot_state.json", {})
    if not isinstance(state, dict):
        state = {}
    stamp = str(state.get("broker_time") or "")
    offset = state.get("broker_utc_offset")
    offset_value = int(offset) if isinstance(offset, (int, float)) and not isinstance(offset, bool) else None
    date_part, _, time_part = stamp.partition("T")
    return {
        "broker_date": (str(state.get("date") or "") or date_part) or None,
        "broker_time": time_part or None,
        "broker_utc_offset": offset_value,
        "broker_clock_verified": bool(stamp) and offset_value is not None,
    }


def today_rules(locale: str = "VN") -> dict[str, Any]:
    """The published rule contract for the current broker day (read-only)."""
    selected = _normalise_locale(locale)
    contract = _read_json(_rule_contract_path(), {})
    if not isinstance(contract, dict):
        contract = {}
    payload: dict[str, Any] = {
        "available": bool(contract),
        "source": "signal_rule_contract",
        "locale": selected,
        "reason": None if contract else "rule_contract_unavailable",
        "logic_version": _scalar(contract.get("logic_version")),
        "public_slots": _public_slots(contract.get("public_slots")),
        "startup_summary": str(contract.get("startup_summary") or "")[:_MAX_TEXT * 4],
        "rules": _rule_strings(contract.get("rules"), selected),
        **_broker_state(),
    }
    if payload["available"] and not payload["rules"]:
        payload["reason"] = "no_rules_for_locale"
    return payload
