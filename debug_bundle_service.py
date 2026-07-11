# -*- coding: utf-8 -*-
"""Build redacted debug ZIP bundles (no raw secrets by default)."""
from __future__ import annotations

import io
import json
import os
import re
import zipfile
from typing import Any, Dict, Iterable, List, Optional, Tuple

SECRET_KEY_RE = re.compile(
    r"(token|api[_-]?key|secret|password|passwd|chat[_-]?id|tele_chat|admin|login|auth)",
    re.I,
)


def redact_value(key: str, value: Any) -> Any:
    if isinstance(value, dict):
        return {k: redact_value(k, v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_value(key, v) for v in value]
    if SECRET_KEY_RE.search(str(key or "")):
        if value in (None, "", 0, False):
            return value
        return "***REDACTED***"
    if isinstance(value, str) and len(value) > 20:
        # Long opaque strings that look like tokens
        if re.fullmatch(r"[A-Za-z0-9_:\-]{24,}", value):
            if any(s in key.lower() for s in ("token", "key", "secret", "path")) or ":" in value:
                if "token" in key.lower() or "key" in key.lower() or "secret" in key.lower():
                    return "***REDACTED***"
    return value


def redact_json_obj(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: redact_value(k, v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact_json_obj(v) for v in obj]
    return obj


def load_and_redact_json(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return json.dumps(redact_json_obj(data), ensure_ascii=False, indent=2)
    except Exception:
        return None


def list_export_candidates(root: str) -> List[Tuple[str, str]]:
    """Return [(arcname, abs_path), ...] of files considered for export."""
    names = [
        "logs/app.log",
        "config.json",
        "profiles.json",
        "settings.json",
        "scheduled_trades.json",
        "scheduled_close.json",
        "pending_partials.json",
        "session_state.json",
        "signals_log.json",
    ]
    out = []
    for name in names:
        p = os.path.join(root, name.replace("/", os.sep))
        if os.path.exists(p):
            out.append((name, p))
    return out


def build_debug_bundle_bytes(
    root: str,
    *,
    include_account_raw: bool = False,
    selected: Optional[Iterable[str]] = None,
) -> bytes:
    """Build zip in memory. Sensitive JSON is redacted unless include_account_raw."""
    candidates = {arc: path for arc, path in list_export_candidates(root)}
    if selected is not None:
        selected_set = set(selected)
        candidates = {a: p for a, p in candidates.items() if a in selected_set}

    sensitive = {"config.json", "profiles.json", "settings.json"}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "EXPORT_README.txt",
            (
                "OAK Debug Bundle\n"
                f"include_account_raw={include_account_raw}\n"
                "Sensitive JSON fields (token/api_key/chat_id/admin/login/...) "
                "are redacted unless include_account_raw=True.\n"
            ),
        )
        for arc, path in candidates.items():
            base = os.path.basename(arc)
            if base.endswith(".json") and base in sensitive and not include_account_raw:
                redacted = load_and_redact_json(path)
                if redacted is not None:
                    zf.writestr(arc.replace(".json", ".redacted.json"), redacted)
                    continue
            # logs / state / raw override
            try:
                zf.write(path, arcname=arc)
            except Exception:
                pass
    return buf.getvalue()
