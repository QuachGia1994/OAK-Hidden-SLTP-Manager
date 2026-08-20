# -*- coding: utf-8 -*-
"""Publish normalized H1 scanner state to the public Upstash feed."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_SCHEMA = 2
KEY_PREFIX = "robot-sltp:public:h1-signals:"
TARGET_BASES = ("XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY")
PATTERN_KINDS = {"sw2", "sw3Pure", "sw3Alternating", "sw6CombinedPure"}


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
    """Normalize persisted scanner state into the web transport contract."""
    if not isinstance(state, dict) or state.get("version") != 2 or not isinstance(state.get("days"), dict):
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
                for alert in sorted(
                    (row for row in alerts if isinstance(row, dict) and isinstance(row.get("slotHour"), int)),
                    key=lambda row: int(row["slotHour"]),
                ):
                    signal = str(alert.get("symbolH1Signal") or "").strip().upper()
                    gbp_signal = str(alert.get("gbpusdH1Signal") or "").strip().upper()
                    pattern_kind = str(alert.get("patternKind") or "").strip()
                    if signal not in {"BUY", "SELL"} or pattern_kind not in PATTERN_KINDS:
                        # Fail closed for incomplete legacy rows. Scanner normalizes
                        # them before publication whenever enough market data exists.
                        continue
                    public_alerts.append({
                        "slotHour": int(alert["slotHour"]),
                        "pattern": str(alert.get("pattern") or ""),
                        "patternKind": pattern_kind,
                        "bars": [str(value) for value in (alert.get("bars") or []) if isinstance(value, str)],
                        "symbol": str(alert.get("symbol") or base),
                        "profile": str(alert.get("profile") or profile),
                        "signal": signal,
                        "gbpusdSignal": gbp_signal if gbp_signal in {"BUY", "SELL"} else "",
                        "gbpusdBaseHour": alert.get("gbpusdBaseHour") if isinstance(alert.get("gbpusdBaseHour"), int) else None,
                        "gbpusdBaseDirection": str(alert.get("gbpusdBaseDirection") or "").strip().upper(),
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
