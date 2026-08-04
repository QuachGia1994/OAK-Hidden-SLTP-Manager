# -*- coding: utf-8 -*-
"""Settings + service-status queries for the supervisor (Phase 6, §9).

settings.json lives at the repo root. Only whitelisted, non-secret keys are
exposed to the UI; ntfy_topic etc. are masked on read (never sent to React).
"""
import json
import os
from pathlib import Path

from .profiles import profiles_path

#: Keys editable from the Settings UI (all non-secret).
_EDITABLE_KEYS = ("lang", "theme", "ghost_mode_active",
                  "stock_client_id", "stock_capital", "stock_hurdle_bps")

#: Keys readable but masked (never sent raw to the frontend).
_MASKED_KEYS = ("ntfy_topic",)

#: Known side services surfaced on the Diagnostics page.
SERVICES = (
    ("telegram", "MiMo Telegram Bot"),
    ("mimo_worker", "MiMo Worker"),
    ("factcheck_worker", "Fact Check Worker"),
    ("screener", "Stock Screener"),
    ("signal_bot", "MT5 Account Audit Service"),
)


def _settings_path() -> Path:
    return profiles_path().parent / "settings.json"


def load_settings() -> dict:
    try:
        data = json.loads(_settings_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _atomic_write_settings(settings: dict) -> None:
    path = _settings_path()
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def public_settings() -> dict:
    """Settings safe for the UI: editable keys + masked flags for secrets."""
    raw = load_settings()
    out = {}
    for key in _EDITABLE_KEYS:
        out[key] = raw.get(key)
    for key in _MASKED_KEYS:
        out[key] = bool(raw.get(key))  # presence flag only — never the value
    return out


def update_settings(updates: dict) -> dict:
    """Merge whitelisted settings (rejects secret keys outright)."""
    settings = load_settings()
    for key, value in (updates or {}).items():
        if key in _EDITABLE_KEYS:
            settings[key] = value
    _atomic_write_settings(settings)
    return public_settings()


def services_list() -> list:
    """Service cards for Diagnostics: name + enabled flag + configured flag.

    "configured" = the service has what it needs in settings/profiles; the
    actual running state lives in the Rust shell / process supervisor.
    """
    settings = load_settings()
    telegram_configured = bool(settings.get("ntfy_topic")) or bool(
        (profiles_path().parent / "config.json").exists()
    )
    result = []
    for key, label in SERVICES:
        if key == "telegram":
            enabled = telegram_configured
        elif key == "screener":
            enabled = bool(settings.get("stock_client_id"))
        else:
            enabled = True
        result.append({"key": key, "label": label,
                       "enabled": enabled, "configured": enabled})
    return result
