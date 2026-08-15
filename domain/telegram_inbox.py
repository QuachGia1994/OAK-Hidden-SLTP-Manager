from __future__ import annotations

import json
import time
from pathlib import Path

from domain.file_lock import FileLock


def _load_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return []
    return [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []


def append_inbox_update(path: str | Path, text: str, chat_id: int | str, source: str = "Bridge") -> dict:
    inbox_path = Path(path)
    lock_path = str(inbox_path) + ".lock"
    with FileLock(lock_path, timeout=3) as acquired:
        if acquired is None:
            raise RuntimeError("Telegram inbox lock timed out")
        rows = _load_rows(inbox_path)
        existing_ids = [int(row.get("update_id") or 0) for row in rows]
        update_id = max(int(time.time() * 1000), max(existing_ids, default=0) + 1)
        now_seconds = int(time.time())
        update = {
            "update_id": update_id,
            "message": {
                "message_id": update_id,
                "from": {"id": chat_id, "first_name": source},
                "chat": {"id": chat_id},
                "date": now_seconds,
                "text": text,
            },
        }
        rows.append(update)
        inbox_path.write_text(
            json.dumps(rows[-50:], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return update
