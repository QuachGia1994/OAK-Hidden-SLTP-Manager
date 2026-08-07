# -*- coding: utf-8 -*-
"""Redacted diagnostics queries for the Tauri desktop shell."""
from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .accounts import _ensure_imports
from .profiles import _data_root, load_profiles

_ensure_imports()

_LEVEL_MARKERS = {
    "ERROR": ("ERROR", "[ERR", "TRACEBACK", "EXCEPTION", "FAILED", "CRITICAL"),
    "WARN": ("WARN", "WARNING", "CAUTION"),
    "INFO": ("INFO", "[OK]", "START", "CONNECTED", "RUNNING"),
}
_SECRET_RE = re.compile(
    r"(?i)\b(token|password|secret|api[_-]?key)\b\s*[:=]\s*([^\s,;]+)"
)


def _redact(line: str) -> str:
    return _SECRET_RE.sub(lambda match: f"{match.group(1)}=[REDACTED]", line)


def _latest_log() -> Path | None:
    root = _data_root()
    candidates: list[Path] = []
    for folder in (root, root / "logs"):
        if not folder.is_dir():
            continue
        candidates.extend(path for path in folder.glob("*.log") if path.is_file())
    return max(candidates, key=lambda path: path.stat().st_mtime) if candidates else None


def _matches(line: str, query: str, level: str) -> bool:
    lower = line.lower()
    terms = [term.lower() for term in str(query or "").split() if term.strip()]
    if any(term not in lower for term in terms):
        return False
    normalized = str(level or "ALL").upper()
    if normalized == "ALL":
        return True
    return any(marker in line.upper() for marker in _LEVEL_MARKERS.get(normalized, ()))


def tail(lines: int = 200, query: str = "", level: str = "ALL") -> dict[str, Any]:
    """Return a bounded redacted tail from the newest app log."""
    requested = max(1, min(int(lines), 800))
    path = _latest_log()
    if path is None:
        return {"lines": [], "truncated": False, "requested": requested, "latest_log": None}
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"lines": [], "truncated": False, "requested": requested, "latest_log": path.name}
    filtered = [_redact(line) for line in raw.splitlines() if _matches(line, query, level)]
    truncated = len(filtered) > requested
    return {
        "lines": filtered[-requested:],
        "truncated": truncated,
        "requested": requested,
        "latest_log": path.name,
    }


def summary(*, selected: str = "", query: str = "", level: str = "ALL") -> dict[str, Any]:
    latest = _latest_log()
    current = tail(800, query=query, level=level)
    return {
        "mode": "frozen" if getattr(sys, "frozen", False) else "source",
        "python": sys.version.split()[0],
        "root_name": _data_root().name,
        "profiles": len(load_profiles()),
        "settings": (_data_root() / "settings.json").is_file(),
        "selected": selected or None,
        "latest_log": latest.name if latest else None,
        "visible_lines": len(current["lines"]),
        "level": str(level or "ALL").upper(),
        "query": query or None,
    }


def export_bundle() -> dict[str, Any]:
    """Write a redacted support bundle inside the app data root."""
    from services.debug_bundle_service import build_debug_bundle_bytes

    root = _data_root()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = root / "dist" / "debug-bundles" / f"oak_debug_bundle_{timestamp}.zip"
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = build_debug_bundle_bytes(str(root), include_account_raw=False)
    temp = target.with_suffix(".zip.tmp")
    temp.write_bytes(payload)
    os.replace(temp, target)
    return {
        "exported": True,
        "file_name": target.name,
        "size_bytes": len(payload),
        "path": str(target),
        "directory": str(target.parent),
    }
