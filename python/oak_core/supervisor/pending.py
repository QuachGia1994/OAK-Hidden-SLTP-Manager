# -*- coding: utf-8 -*-
"""Safe, profile-scoped access to the legacy pending JSON files.

The Native Qt shell reads these files directly.  The Tauri shell must not: all
file access stays in oak-core and every mutation derives its path from a
validated profile name.  Row ids are opaque hashes so the frontend never gets
an absolute path or a write primitive.
"""
from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .accounts import _ensure_imports
from .profiles import _data_root, load_profiles

_ensure_imports()
from domain.file_lock import FileLock  # noqa: E402

_DONE_STATUSES = {"done", "executed", "closed", "expired", "cancelled", "canceled"}
_SENSITIVE_KEYS = {"token", "password", "secret", "api_key", "apikey"}


def _safe_profile_filename(profile_name: str) -> str:
    raw = str(profile_name or "default").strip() or "default"
    safe = "".join(char for char in raw if char.isalnum() or char in (" ", "-", "_"))
    return safe.strip() or "default"


def _file_specs(profile_name: str) -> list[tuple[str, Path, str]]:
    safe = _safe_profile_filename(profile_name)
    root = _data_root()
    return [
        ("entries", root / f"waiting_{safe}.json", "list"),
        ("scheduled closes", root / f"scheduled_close_{safe}.json", "list"),
        ("partials", root / f"pending_partials_{safe}.json", "dict"),
    ]


def _require_profile(profile_name: str) -> str:
    profile = str(profile_name or "").strip()
    if not profile:
        raise ValueError("profile is required")
    if profile not in load_profiles():
        raise KeyError(profile)
    return profile


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(f"{path.suffix}.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    lock = FileLock(f"{path}.lock", timeout=3.0)
    acquired = lock.__enter__()
    if acquired is None:
        raise TimeoutError(f"timed out locking {path.name}")
    try:
        yield
    finally:
        lock.__exit__(None, None, None)


def _public_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _public_value(item)
            for key, item in value.items()
            if not str(key).startswith("_") and str(key).lower() not in _SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_public_value(item) for item in value]
    return value


def _row_id(kind: str, key: str, index: int, value: Any) -> str:
    payload = json.dumps(
        {"kind": kind, "key": key, "index": index, "value": _public_value(value)},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:24]


def _normalise_row(kind: str, key: str, index: int, value: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"kind": kind}
    if isinstance(value, dict):
        row.update(_public_value(value))
    else:
        row["value"] = _public_value(value)
    if kind == "partials" and "ticket" not in row:
        row["ticket"] = key
    row["id"] = _row_id(kind, key, index, value)
    row["file_name"] = ""
    row["status"] = str(row.get("status") or "waiting")
    return row


def _rows(kind: str, path: Path, data: Any, shape: str) -> list[tuple[dict[str, Any], str, int]]:
    result: list[tuple[dict[str, Any], str, int]] = []
    if shape == "dict" and isinstance(data, dict):
        for index, (key, value) in enumerate(data.items()):
            row = _normalise_row(kind, str(key), index, value)
            row["file_name"] = path.name
            result.append((row, str(key), index))
    elif isinstance(data, list):
        for index, value in enumerate(data):
            row = _normalise_row(kind, str(index), index, value)
            row["file_name"] = path.name
            result.append((row, str(index), index))
    return result


def summary(profile_name: str) -> dict[str, Any]:
    """Return bounded, public-safe pending rows for one profile."""
    profile = _require_profile(profile_name)
    files: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    for kind, path, shape in _file_specs(profile):
        data = _read_json(path, {} if shape == "dict" else [])
        rows = _rows(kind, path, data, shape)
        files.append({"name": path.name, "count": len(rows)})
        items.extend(row for row, _key, _index in rows)
    waiting = sum(1 for item in items if str(item.get("status", "waiting")).lower() not in _DONE_STATUSES)
    done = len(items) - waiting
    return {
        "profile": profile,
        "files": files,
        "items": items[:100],
        "total": len(items),
        "waiting": waiting,
        "done": done,
    }


def delete_item(profile_name: str, item_id: str) -> dict[str, Any]:
    """Delete one row by opaque id after reloading the selected file."""
    profile = _require_profile(profile_name)
    target = str(item_id or "").strip()
    if not target:
        raise ValueError("item_id is required")
    for kind, path, shape in _file_specs(profile):
        with _locked(path):
            data = _read_json(path, {} if shape == "dict" else [])
            rows = _rows(kind, path, data, shape)
            match = next((entry for entry in rows if entry[0].get("id") == target), None)
            if match is None:
                continue
            _row, key, index = match
            if shape == "dict" and isinstance(data, dict):
                data.pop(key, None)
            elif isinstance(data, list) and 0 <= index < len(data):
                data.pop(index)
            else:
                continue
            _write_json(path, data)
            return {"deleted": True, "id": target, "file": path.name}
    return {"deleted": False, "id": target}


def clear_done(profile_name: str) -> dict[str, Any]:
    """Remove completed rows from list-based pending files only."""
    profile = _require_profile(profile_name)
    removed = 0
    for _kind, path, shape in _file_specs(profile):
        if shape != "list":
            continue
        with _locked(path):
            data = _read_json(path, [])
            if not isinstance(data, list):
                continue
            kept = []
            for value in data:
                status = str(value.get("status") if isinstance(value, dict) else "").lower()
                if status in _DONE_STATUSES:
                    removed += 1
                else:
                    kept.append(value)
            if len(kept) != len(data):
                _write_json(path, kept)
    return {"cleared": removed}
