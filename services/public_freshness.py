# -*- coding: utf-8 -*-
"""Public portal data freshness contract (transparency, not trading urgency)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

# Age thresholds in seconds — covered by unit tests.
FRESHNESS_LIVE_SECONDS = 30
FRESHNESS_DEGRADED_SECONDS = 120
FRESHNESS_STALE_SECONDS = 600

STATUS_LIVE = "LIVE"
STATUS_DEGRADED = "DEGRADED"
STATUS_STALE = "STALE"
STATUS_UNAVAILABLE = "UNAVAILABLE"

SOURCE_MT5_LIVE = "MT5_LIVE"
SOURCE_EQUITY_SAMPLE = "EQUITY_SAMPLE"
SOURCE_CHECKPOINT = "CHECKPOINT"
SOURCE_STORE = "TRADE_AUDIT_STORE"
SOURCE_NONE = "NONE"


def parse_utc(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def classify_freshness(observed_at_utc, now_utc=None) -> dict:
    """Return public-safe freshness metadata from an observation timestamp.

    Never invents a current timestamp to hide stale data: if observed_at is
    missing, status is UNAVAILABLE.
    """
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    observed = parse_utc(observed_at_utc)
    if observed is None:
        return {
            "source_status": STATUS_UNAVAILABLE,
            "observed_at_utc": None,
            "data_age_seconds": None,
            "freshness_thresholds": {
                "live": FRESHNESS_LIVE_SECONDS,
                "degraded": FRESHNESS_DEGRADED_SECONDS,
                "stale": FRESHNESS_STALE_SECONDS,
            },
        }
    age = max(0.0, (now - observed).total_seconds())
    if age <= FRESHNESS_LIVE_SECONDS:
        status = STATUS_LIVE
    elif age <= FRESHNESS_DEGRADED_SECONDS:
        status = STATUS_DEGRADED
    elif age <= FRESHNESS_STALE_SECONDS:
        status = STATUS_STALE
    else:
        status = STATUS_STALE  # still labeled STALE when older than threshold
        if age > FRESHNESS_STALE_SECONDS:
            status = STATUS_STALE
    # Beyond stale window still STALE (data exists); UNAVAILABLE only when no ts.
    return {
        "source_status": status,
        "observed_at_utc": observed.isoformat(),
        "data_age_seconds": int(age),
        "freshness_thresholds": {
            "live": FRESHNESS_LIVE_SECONDS,
            "degraded": FRESHNESS_DEGRADED_SECONDS,
            "stale": FRESHNESS_STALE_SECONDS,
        },
    }


def build_freshness_envelope(
    *,
    observed_at_utc,
    published_at_utc=None,
    source: str = SOURCE_STORE,
    now_utc=None,
) -> dict:
    """Combine observation + publish timestamps into a public envelope."""
    now = now_utc or datetime.now(timezone.utc)
    published = parse_utc(published_at_utc) or now
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    meta = classify_freshness(observed_at_utc, now_utc=now)
    meta["published_at_utc"] = published.isoformat()
    meta["source"] = source or SOURCE_NONE
    return meta
