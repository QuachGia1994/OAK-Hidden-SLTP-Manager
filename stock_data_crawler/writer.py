"""Write stock data to static JSON files in public/stock-data/{SYMBOL}/."""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger("stock_data_crawler")


def _write_json(path: str, data: dict[str, Any]) -> bool:
    """Write JSON file, creating directories as needed. Returns True if file changed."""
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Read existing file to check for changes
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if existing == data:
                return False
        except (json.JSONDecodeError, OSError):
            pass

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True


def write_profile(profile: Any, output_dir: str) -> bool:
    path = os.path.join(output_dir, "profile.json")
    return _write_json(path, profile.to_dict())


def write_reports(reports: Any, output_dir: str) -> bool:
    path = os.path.join(output_dir, "reports.json")
    return _write_json(path, reports.to_dict())


def write_dividends(dividends: Any, output_dir: str) -> bool:
    path = os.path.join(output_dir, "dividends.json")
    return _write_json(path, dividends.to_dict())


def write_foreign(foreign: Any, output_dir: str) -> bool:
    path = os.path.join(output_dir, "foreign-trading.json")
    return _write_json(path, foreign.to_dict())
