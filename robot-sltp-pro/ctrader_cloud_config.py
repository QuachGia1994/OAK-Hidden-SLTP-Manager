from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlencode


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
        raw_account = (os.environ.get("OAK_CTRADER_ACCOUNT_ID") or "").strip()
        try:
            account_id = int(raw_account or 0)
        except ValueError:
            account_id = 0
        environment = (os.environ.get("OAK_CTRADER_ENV") or "demo").strip().lower()
        if environment not in {"demo", "live"}:
            environment = "demo"
        return cls(
            client_id=(os.environ.get("OAK_CTRADER_CLIENT_ID") or "").strip(),
            client_secret=(os.environ.get("OAK_CTRADER_CLIENT_SECRET") or "").strip(),
            access_token=(os.environ.get("OAK_CTRADER_ACCESS_TOKEN") or "").strip(),
            refresh_token=(os.environ.get("OAK_CTRADER_REFRESH_TOKEN") or "").strip(),
            account_id=account_id,
            environment=environment,
            broker=(os.environ.get("OAK_CTRADER_BROKER") or "ICMarkets").strip() or "ICMarkets",
        )

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
