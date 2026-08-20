from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from ctrader_cloud_config import CTraderCloudConfig
from ctrader_market_data import (
    _extract_message,
    canonical_symbol_name,
    choose_authorized_account,
    resolve_light_symbols,
    trendbar_to_candle,
)
from h1_market_data import build_h1_snapshot_payload, icmarkets_server_wall_epoch
from market_data_provider import Candle


H1_PARITY_SYMBOLS = ("GBPUSD", "XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY")


@dataclass(frozen=True, slots=True)
class CTraderH1SnapshotResult:
    candles_by_symbol: dict[str, tuple[Candle, ...]]
    account_id: int
    environment: str
    broker: str

    def as_payload(self, *, broker_date: str | None = None) -> dict[str, Any]:
        return build_h1_snapshot_payload(
            provider=(
                f"ctrader-open-api-h1:{canonical_symbol_name(self.broker)}:"
                f"{self.environment}:{self.account_id}"
            ),
            candles_by_symbol=self.candles_by_symbol,
            broker_date=broker_date,
            metadata={
                "accountId": self.account_id,
                "environment": self.environment,
                "broker": self.broker,
                "source": "ctrader-open-api",
                "timestampMode": "icmarkets-mt5-server-wall",
                "scope": "H1 scanner parity",
            },
        )


def h1_rows_to_server_wall(rows: Sequence[Any], digits: int) -> tuple[Candle, ...]:
    converted = []
    for row in rows:
        candle = trendbar_to_candle(row, digits)
        converted.append(Candle(
            time=icmarkets_server_wall_epoch(candle.time),
            open=candle.open,
            high=candle.high,
            low=candle.low,
            close=candle.close,
        ))
    return tuple(sorted(converted, key=lambda candle: candle.time))


def collect_h1_snapshot_deferred(
    reactor: Any,
    config: CTraderCloudConfig,
    *,
    symbols: Sequence[str] = H1_PARITY_SYMBOLS,
    start_epoch: int,
    end_epoch: int,
):
    """Fetch raw cTrader H1 trendbars for scanner parity; no H4 reconstruction."""
    missing = config.missing_for_market_data()
    if missing:
        raise RuntimeError(f"cTrader market data is not configured: {', '.join(missing)}")

    from ctrader_open_api import Client, Protobuf, TcpProtocol
    from ctrader_open_api.endpoints import EndPoints
    from ctrader_open_api.messages.OpenApiMessages_pb2 import (
        ProtoOAAccountAuthReq,
        ProtoOAApplicationAuthReq,
        ProtoOAGetAccountListByAccessTokenReq,
        ProtoOAGetTrendbarsReq,
        ProtoOASymbolByIdReq,
        ProtoOASymbolsListReq,
    )
    from ctrader_open_api.messages.OpenApiModelMessages_pb2 import ProtoOATrendbarPeriod
    from twisted.internet.defer import Deferred, inlineCallbacks

    host = EndPoints.PROTOBUF_LIVE_HOST if config.environment == "live" else EndPoints.PROTOBUF_DEMO_HOST
    client = Client(host, EndPoints.PROTOBUF_PORT, TcpProtocol)
    connected = Deferred()

    def on_connected(_client: Any) -> None:
        if not connected.called:
            connected.callback(True)

    def on_disconnected(_client: Any, reason: Any) -> None:
        if not connected.called:
            connected.errback(RuntimeError(f"cTrader disconnected before auth: {reason}"))

    client.setConnectedCallback(on_connected)
    client.setDisconnectedCallback(on_disconnected)

    @inlineCallbacks
    def run():
        try:
            client.startService()
            yield connected

            app_auth = ProtoOAApplicationAuthReq()
            app_auth.clientId = config.client_id
            app_auth.clientSecret = config.client_secret
            yield client.send(app_auth)

            account_list_req = ProtoOAGetAccountListByAccessTokenReq()
            account_list_req.accessToken = config.access_token
            account_list_raw = yield client.send(account_list_req)
            account_list = _extract_message(Protobuf, account_list_raw)
            account = choose_authorized_account(
                getattr(account_list, "ctidTraderAccount", ()),
                account_id=config.account_id,
                environment=config.environment,
                broker_hint=config.broker,
            )
            account_id = int(account.ctidTraderAccountId)

            account_auth = ProtoOAAccountAuthReq()
            account_auth.ctidTraderAccountId = account_id
            account_auth.accessToken = config.access_token
            yield client.send(account_auth)

            symbol_list_req = ProtoOASymbolsListReq()
            symbol_list_req.ctidTraderAccountId = account_id
            symbol_list_req.includeArchivedSymbols = False
            symbol_list_raw = yield client.send(symbol_list_req)
            symbol_list = _extract_message(Protobuf, symbol_list_raw)
            light = resolve_light_symbols(getattr(symbol_list, "symbol", ()), symbols)

            selected_ids = [int(getattr(light[canonical_symbol_name(base)], "symbolId")) for base in symbols]
            full_req = ProtoOASymbolByIdReq()
            full_req.ctidTraderAccountId = account_id
            full_req.symbolId.extend(selected_ids)
            full_raw = yield client.send(full_req)
            full_response = _extract_message(Protobuf, full_raw)
            full_by_id = {
                int(getattr(row, "symbolId", 0) or 0): row
                for row in getattr(full_response, "symbol", ())
            }

            candles_by_symbol: dict[str, tuple[Candle, ...]] = {}
            for base in symbols:
                canonical = canonical_symbol_name(base)
                symbol_id = int(getattr(light[canonical], "symbolId"))
                full_symbol = full_by_id.get(symbol_id)
                if full_symbol is None:
                    raise RuntimeError(f"Full cTrader symbol metadata missing: {canonical}")
                digits = int(getattr(full_symbol, "digits", 5) or 5)

                req = ProtoOAGetTrendbarsReq()
                req.ctidTraderAccountId = account_id
                req.symbolId = symbol_id
                req.period = ProtoOATrendbarPeriod.Value("H1")
                req.fromTimestamp = max(0, int(start_epoch)) * 1000
                req.toTimestamp = int(end_epoch) * 1000
                raw = yield client.send(req)
                response = _extract_message(Protobuf, raw)
                rows = tuple(getattr(response, "trendbar", ()))
                candles = h1_rows_to_server_wall(rows, digits)
                if not candles:
                    raise RuntimeError(f"No H1 trendbars returned for {canonical}")
                candles_by_symbol[canonical] = candles

            return CTraderH1SnapshotResult(
                candles_by_symbol=candles_by_symbol,
                account_id=account_id,
                environment=config.environment,
                broker=config.broker,
            )
        finally:
            try:
                client.stopService()
            except Exception:
                pass

    return run()
