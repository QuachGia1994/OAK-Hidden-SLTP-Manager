from __future__ import annotations

import json
import os
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True, slots=True)
class CTraderCloudConfig:
    """Secrets/config required by the future IC Markets cTrader cloud adapter.

    Values are read from environment variables only. Secrets are never written
    into profiles.json or returned by status helpers.
    """

    client_id: str
    client_secret: str
    access_token: str
    refresh_token: str
    account_id: int
    environment: str = "demo"
    broker: str = "ICMarkets"

    @classmethod
    def from_env(cls) -> "CTraderCloudConfig":
        return cls.from_mapping({
            "clientId": os.environ.get("OAK_CTRADER_CLIENT_ID") or "",
            "clientSecret": os.environ.get("OAK_CTRADER_CLIENT_SECRET") or "",
            "accessToken": os.environ.get("OAK_CTRADER_ACCESS_TOKEN") or "",
            "refreshToken": os.environ.get("OAK_CTRADER_REFRESH_TOKEN") or "",
            "accountId": os.environ.get("OAK_CTRADER_ACCOUNT_ID") or "",
            "environment": os.environ.get("OAK_CTRADER_ENV") or "demo",
            "broker": os.environ.get("OAK_CTRADER_BROKER") or "ICMarkets",
        })

    @classmethod
    def from_mapping(cls, payload: dict[str, object]) -> "CTraderCloudConfig":
        try:
            account_id = int(payload.get("accountId") or 0)
        except (TypeError, ValueError):
            account_id = 0
        environment = str(payload.get("environment") or "demo").strip().lower()
        if environment not in {"demo", "live"}:
            environment = "demo"
        return cls(
            client_id=str(payload.get("clientId") or "").strip(),
            client_secret=str(payload.get("clientSecret") or "").strip(),
            access_token=str(payload.get("accessToken") or "").strip(),
            refresh_token=str(payload.get("refreshToken") or "").strip(),
            account_id=account_id,
            environment=environment,
            broker=str(payload.get("broker") or "ICMarkets").strip() or "ICMarkets",
        )

    @classmethod
    def from_control_plane(cls, url: str, api_key: str, timeout: float = 10.0) -> "CTraderCloudConfig":
        if not url or not api_key:
            raise RuntimeError("cTrader control-plane URL and DASHBOARD_API_KEY are required")
        request = Request(
            url,
            headers={"x-api-key": api_key, "Accept": "application/json"},
            method="GET",
        )
        with urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, dict) or not payload.get("ok"):
            raise RuntimeError("cTrader control-plane session request failed")
        return cls.from_mapping(payload)

    def missing_for_market_data(self) -> tuple[str, ...]:
        missing: list[str] = []
        if not self.client_id:
            missing.append("OAK_CTRADER_CLIENT_ID")
        if not self.client_secret:
            missing.append("OAK_CTRADER_CLIENT_SECRET")
        if not self.access_token:
            missing.append("OAK_CTRADER_ACCESS_TOKEN")
        if self.account_id <= 0:
            missing.append("OAK_CTRADER_ACCOUNT_ID")
        return tuple(missing)

    def status(self) -> dict[str, object]:
        missing = self.missing_for_market_data()
        return {
            "provider": "ctrader-open-api",
            "broker": self.broker,
            "environment": self.environment,
            "configured": not missing,
            "refreshTokenConfigured": bool(self.refresh_token),
            "missing": list(missing),
        }


def authorization_url(client_id: str, redirect_uri: str, *, trading: bool = False) -> str:
    """Build Spotware OAuth grant URL without exposing any client secret."""

    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "trading" if trading else "accounts",
            "product": "web",
        }
    )
    return f"https://id.ctrader.com/my/settings/openapi/grantingaccess/?{query}"
