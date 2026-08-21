# -*- coding: utf-8 -*-
"""Publish normalized H1 fallback-scanner state to the public Upstash feed."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_SCHEMA = 7
KEY_PREFIX = "robot-sltp:public:h1-signals:"
TARGET_BASES = ("XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY")
PATTERN_KINDS = {"sw2", "sw3Pure", "sw3Normal"}
SCANNER_BASES = {"AUDUSD", "GBPUSD"}


def _load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def build_public_h1_feed(
    state: dict[str, Any],
    profile: str,
    *,
    published_at: str | None = None,
) -> dict[str, Any]:
    """Normalize persisted fallback state into public scanner schema v7."""
    if not isinstance(state, dict) or state.get("version") != 7 or not isinstance(state.get("days"), dict):
        raise ValueError("Invalid H1 scanner state")

    public_days: dict[str, Any] = {}
    for day_key in sorted(state["days"]):
        day_state = state["days"].get(day_key)
        if not isinstance(day_state, dict):
            continue
        symbols = day_state.get("symbols")
        if not isinstance(symbols, dict):
            continue
        public_symbols: dict[str, Any] = {}
        for base in TARGET_BASES:
            symbol_state = symbols.get(base)
            if not isinstance(symbol_state, dict):
                continue
            public_alerts = []
            alerts = symbol_state.get("alerts")
            if isinstance(alerts, list):
                rows = sorted(
                    (row for row in alerts if isinstance(row, dict) and isinstance(row.get("slotHour"), int)),
                    key=lambda row: int(row["slotHour"]),
                )
                for alert in rows:
                    signal = str(alert.get("symbolH1Signal") or "").strip().upper()
                    base_signal = str(alert.get("baseH1Signal") or "").strip().upper()
                    base_direction = str(alert.get("baseDirection") or "").strip().upper()
                    pattern_kind = str(alert.get("patternKind") or "").strip()
                    scanner_base = str(alert.get("scannerBase") or "").strip().upper()
                    base_symbol = str(alert.get("baseSymbol") or "").strip().upper()
                    base_hour = alert.get("baseHour")
                    if (
                        signal not in {"BUY", "SELL"}
                        or base_signal not in {"BUY", "SELL"}
                        or base_direction not in {"T", "G"}
                        or pattern_kind not in PATTERN_KINDS
                        or scanner_base not in SCANNER_BASES
                        or not base_symbol
                        or not isinstance(base_hour, int)
                    ):
                        continue
                    public_alerts.append({
                        "slotHour": int(alert["slotHour"]),
                        "pattern": str(alert.get("pattern") or ""),
                        "patternKind": pattern_kind,
                        "bars": [str(value) for value in (alert.get("bars") or []) if isinstance(value, str)],
                        "symbol": str(alert.get("symbol") or base),
                        "profile": str(alert.get("profile") or profile),
                        "scannerBase": scanner_base,
                        "scannerSymbol": str(alert.get("scannerSymbol") or scanner_base),
                        "baseSymbol": base_symbol,
                        "baseSignal": base_signal,
                        "baseHour": base_hour,
                        "baseDirection": base_direction,
                        "signal": signal,
                    })
            public_symbols[base] = {"alerts": public_alerts}
        public_days[str(day_key)] = {"symbols": public_symbols}

    return {
        "schemaVersion": PUBLIC_SCHEMA,
        "profile": str(profile or "unknown"),
        "publishedAt": published_at or datetime.now(timezone.utc).isoformat(),
        "hours": list(range(3, 18)),
        "symbols": list(TARGET_BASES),
        "days": public_days,
    }


def publish_h1_signal_state(state: dict[str, Any], profile: str) -> dict[str, Any]:
    """Publish one normalized H1 snapshot. Network failure is raised to caller."""
    _load_dotenv()
    url = os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
    if not url or not token:
        raise RuntimeError("UPSTASH_REDIS_REST_URL/TOKEN are required for H1 public publishing")

    feed = build_public_h1_feed(state, profile)
    value = json.dumps(feed, ensure_ascii=False, separators=(",", ":"))
    profile_key = KEY_PREFIX + str(profile or "unknown")
    for key in (profile_key, KEY_PREFIX + "latest"):
        payload = json.dumps(["SET", key, value]).encode("utf-8")
        request = Request(
            url,
            data=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
        if result.get("result") != "OK":
            raise RuntimeError(f"Upstash H1 publish failed for {key}: {result}")
    return feed
