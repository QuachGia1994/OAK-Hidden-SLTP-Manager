"""Best-effort authenticated publisher for stock advisory dashboard data."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Callable, Mapping
import urllib.request


@dataclass(frozen=True, slots=True)
class DashboardPublisherConfig:
    """Dashboard endpoint and write credential."""

    base_url: str
    api_key: str


@dataclass(frozen=True, slots=True)
class DashboardPushResult:
    """Non-fatal dashboard publication outcome."""

    pushed: bool
    status: str


def load_dashboard_publisher_config(root: Path) -> DashboardPublisherConfig:
    """Resolve dashboard configuration from environment then local config."""
    file_config = _read_config(root / "config.json")
    base_url = os.environ.get("DASHBOARD_API_URL", "") or str(file_config.get("dashboard_url", ""))
    api_key = os.environ.get("DASHBOARD_API_KEY", "") or str(file_config.get("dashboard_api_key", ""))
    return DashboardPublisherConfig(base_url.rstrip("/"), api_key)


def publish_stock_advisory(
    payload: Mapping[str, object],
    config: DashboardPublisherConfig,
    opener: Callable[..., object] = urllib.request.urlopen,
) -> DashboardPushResult:
    """Push one safe advisory payload without making local success depend on web."""
    if not config.base_url:
        return DashboardPushResult(False, "not_configured")
    if payload.get("advisory_only") is not True or payload.get("orders_submitted") is not False:
        return DashboardPushResult(False, "unsafe_payload")
    request = _dashboard_request(payload, config)
    try:
        with opener(request, timeout=15) as response:
            response.read()
    except Exception as error:
        return DashboardPushResult(False, f"failed:{type(error).__name__}")
    return DashboardPushResult(True, "pushed")


def _dashboard_request(payload: Mapping[str, object], config: DashboardPublisherConfig) -> urllib.request.Request:
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["X-API-Key"] = config.api_key
    return urllib.request.Request(
        f"{config.base_url}/api/stock-advisor",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
    )


def _read_config(path: Path) -> Mapping[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, Mapping) else {}
