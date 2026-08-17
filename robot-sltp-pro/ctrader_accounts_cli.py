from __future__ import annotations

import json
import os
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from ctrader_cloud_config import CTraderCloudConfig


def load_config() -> CTraderCloudConfig:
    session_url = (os.environ.get("OAK_CTRADER_SESSION_URL") or "").strip()
    dashboard_key = (os.environ.get("DASHBOARD_API_KEY") or "").strip()
    if session_url:
        separator = "&" if "?" in session_url else "?"
        return CTraderCloudConfig.from_control_plane(
            f"{session_url}{separator}discovery=1",
            dashboard_key,
        )
    return CTraderCloudConfig.from_env()


def run() -> None:
    config = load_config()
    missing = []
    if not config.client_id:
        missing.append("clientId")
    if not config.client_secret:
        missing.append("clientSecret")
    if not config.access_token:
        missing.append("accessToken")
    if missing:
        raise RuntimeError(f"cTrader account discovery is not configured: {', '.join(missing)}")

    from ctrader_open_api import Client, Protobuf, TcpProtocol
    from ctrader_open_api.endpoints import EndPoints
    from ctrader_open_api.messages.OpenApiMessages_pb2 import (
        ProtoOAApplicationAuthReq,
        ProtoOAGetAccountListByAccessTokenReq,
    )
    from twisted.internet import task
    from twisted.internet.defer import Deferred, inlineCallbacks

    host = (
        EndPoints.PROTOBUF_LIVE_HOST
        if config.environment == "live"
        else EndPoints.PROTOBUF_DEMO_HOST
    )
    client = Client(host, EndPoints.PROTOBUF_PORT, TcpProtocol)
    connected = Deferred()

    def on_connected(_client):
        if not connected.called:
            connected.callback(True)

    def on_disconnected(_client, reason):
        if not connected.called:
            connected.errback(RuntimeError(f"cTrader disconnected before auth: {reason}"))

    client.setConnectedCallback(on_connected)
    client.setDisconnectedCallback(on_disconnected)

    @inlineCallbacks
    def collect():
        try:
            client.startService()
            yield connected
            app_auth = ProtoOAApplicationAuthReq()
            app_auth.clientId = config.client_id
            app_auth.clientSecret = config.client_secret
            yield client.send(app_auth)

            request = ProtoOAGetAccountListByAccessTokenReq()
            request.accessToken = config.access_token
            raw = yield client.send(request)
            try:
                response = Protobuf.extract(raw)
            except Exception:
                response = raw

            accounts = []
            for row in getattr(response, "ctidTraderAccount", ()):
                accounts.append({
                    "accountId": int(getattr(row, "ctidTraderAccountId", 0) or 0),
                    "traderLogin": int(getattr(row, "traderLogin", 0) or 0),
                    "environment": "live" if bool(getattr(row, "isLive", False)) else "demo",
                    "broker": str(getattr(row, "brokerTitleShort", "") or ""),
                })
            print(json.dumps({"ok": True, "accounts": accounts}, ensure_ascii=False, indent=2))
            return None
        finally:
            try:
                client.stopService()
            except Exception:
                pass

    def runner(_reactor):
        return collect()

    task.react(runner)


if __name__ == "__main__":
    run()
