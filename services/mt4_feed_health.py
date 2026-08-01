"""Safe readiness check for the local MT4 Feed listener."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass


MT4_FEED_HEALTH_URL = "http://127.0.0.1:5001/mt4-feed/health"


@dataclass(frozen=True)
class MT4FeedHealth:
    """Separate the local HTTP listener state from the live MT4 feed state."""

    listener_available: bool
    data_state: str

    @property
    def feed_connected(self) -> bool:
        """Only a current MT4 heartbeat may unblock signal startup."""
        return self.listener_available and self.data_state == "connected"


def read_mt4_feed_health(timeout: float = 3.0) -> MT4FeedHealth:
    """Read the local health endpoint without treating HTTP 200 as data-ready."""
    try:
        with urllib.request.urlopen(MT4_FEED_HEALTH_URL, timeout=timeout) as response:
            if response.status != 200:
                return MT4FeedHealth(False, "unavailable")
            payload = json.load(response)
    except (OSError, ValueError, json.JSONDecodeError, urllib.error.URLError):
        return MT4FeedHealth(False, "unavailable")
    if not isinstance(payload, dict):
        return MT4FeedHealth(True, "invalid")
    state = str(payload.get("data_state", "unknown")).strip().lower()
    return MT4FeedHealth(True, state or "unknown")
