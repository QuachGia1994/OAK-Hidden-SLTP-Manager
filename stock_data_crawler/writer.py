"""Write stock data to static JSON files in public/stock-data/{SYMBOL}/."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger("stock_data_crawler")


def _read_existing(path: str) -> dict[str, Any] | None:
    """Read existing JSON file, returning None if missing or corrupt."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _write_json(path: str, data: dict[str, Any]) -> bool:
    """Write JSON file, creating directories as needed. Returns True if file changed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    existing = _read_existing(path)
    if existing == data:
        return False

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True


def _write_with_stale_fallback(path: str, data: dict[str, Any] | None) -> bool:
    """Write JSON, falling back to stale cache when data is None.

    If data is None and a previous valid cache exists, marks it as stale
    and keeps it. Returns True if the file was written (new or modified).
    """
    if data is not None:
        return _write_json(path, data)

    existing = _read_existing(path)
    if existing is None:
        return False

    if existing.get("stale"):
        return False  # already stale, no change

    existing["stale"] = True
    logger.info("Keeping stale cache for %s", path)
    return _write_json(path, existing)


def write_profile(profile: Any, output_dir: str) -> bool:
    path = os.path.join(output_dir, "profile.json")
    if profile is None:
        return _write_with_stale_fallback(path, None)
    return _write_json(path, profile.to_dict())


def write_reports(reports: Any, output_dir: str) -> bool:
    path = os.path.join(output_dir, "reports.json")
    if reports is None:
        return _write_with_stale_fallback(path, None)
    return _write_json(path, reports.to_dict())


def write_dividends(dividends: Any, output_dir: str) -> bool:
    path = os.path.join(output_dir, "dividends.json")
    if dividends is None:
        return _write_with_stale_fallback(path, None)
    return _write_json(path, dividends.to_dict())


def write_foreign(foreign: Any, output_dir: str) -> bool:
    path = os.path.join(output_dir, "foreign-trading.json")
    if foreign is None:
        return _write_with_stale_fallback(path, None)
    return _write_json(path, foreign.to_dict())
