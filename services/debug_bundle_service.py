# -*- coding: utf-8 -*-
"""Build redacted debug ZIP bundles (no raw secrets by default)."""
from __future__ import annotations

import io
import json
import os
import re
import zipfile
from typing import Any, Iterable, List, Optional, Tuple

SECRET_KEY_RE = re.compile(
    r"(token|api[_-]?key|secret|password|passwd|chat[_-]?id|tele_chat|admin|login|auth)",
    re.I,
)

# Log line redaction patterns (PII / paths / tokens)
_LOG_REDACT_PATTERNS: List[Tuple[re.Pattern, str]] = [
    # Telegram bot tokens
    (re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{20,}\b"), "***REDACTED_TOKEN***"),
    # Bearer / API keys
    (re.compile(r"(?i)(api[_-]?key|token|authorization|bearer)\s*[:=]\s*\S+"), r"\1=***REDACTED***"),
    # Windows user paths: C:\Users\NAME\...
    (
        re.compile(r"(?i)([A-Za-z]:\\Users\\)([^\\\/\s\"]+)"),
        r"\1***USER***",
    ),
    # Unix home paths
    (re.compile(r"(?i)(/home/)([^/\s\"]+)"), r"\1***USER***"),
    # Login / account numbers after keywords or bare parens
    (
        re.compile(
            r"(?i)(\blogin\b\s*[:=#]?\s*|\#)(\d{5,12})\b"
        ),
        r"\1***LOGIN***",
    ),
    (re.compile(r"\((\d{5,12})\)"), "(***LOGIN***)"),
    # Connected: Name (login) | Broker: ...
    (
        re.compile(r"(Connected:?\s*)[^\n|]+", re.I),
        r"\1***ACCOUNT***",
    ),
    # Broker: Company Name
    (re.compile(r"(?i)(Broker:\s*)([^\n|]+)"), r"\1***BROKER***"),
    # server | #login
    (re.compile(r"(\|\s*#)\d{5,12}\b"), r"\1***LOGIN***"),
]


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


def redact_log_text(text: str) -> str:
    """Strip PII/paths/tokens from log text before export."""
    if not text:
        return text
    out = text
    for pat, repl in _LOG_REDACT_PATTERNS:
        try:
            out = pat.sub(repl, out)
        except Exception:
            continue
    return out


def load_and_redact_log(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return redact_log_text(f.read())
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
    """Build zip in memory.

    By default:
    - sensitive JSON is redacted
    - log files are text-redacted (PII/paths/tokens)
    include_account_raw=True skips redaction (developer / typed confirm only).
    """
    candidates = {arc: path for arc, path in list_export_candidates(root)}
    if selected is not None:
        selected_set = set(selected)
        candidates = {a: p for a, p in candidates.items() if a in selected_set}

    sensitive = {"config.json", "profiles.json", "settings.json"}
    log_names = {"app.log"}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "EXPORT_README.txt",
            (
                "OAK Debug Bundle\n"
                f"include_account_raw={include_account_raw}\n"
                "Default export redacts:\n"
                "  - JSON fields token/api_key/chat_id/admin/login/...\n"
                "  - Log PII (account name, login, Windows user path, bot tokens)\n"
                "Raw export requires explicit developer confirmation in the UI.\n"
            ),
        )
        for arc, path in candidates.items():
            base = os.path.basename(arc)
            if not include_account_raw:
                if base.endswith(".json") and base in sensitive:
                    redacted = load_and_redact_json(path)
                    if redacted is not None:
                        zf.writestr(arc.replace(".json", ".redacted.json"), redacted)
                        continue
                if base in log_names or base.endswith(".log"):
                    redacted_log = load_and_redact_log(path)
                    if redacted_log is not None:
                        zf.writestr(
                            arc.replace(".log", ".redacted.log") if arc.endswith(".log") else arc,
                            redacted_log,
                        )
                        continue
            try:
                zf.write(path, arcname=arc)
            except Exception:
                pass
    return buf.getvalue()
