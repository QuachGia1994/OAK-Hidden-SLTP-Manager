from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from ctrader_cloud_config import CTraderCloudConfig
from h1_market_data import build_h1_snapshot_payload, icmarkets_server_wall_epoch
from market_data_provider import Candle


H1_PARITY_SYMBOLS = ("GBPUSD", "AUDUSD", "EURUSD", "USDCAD", "USDJPY")


def canonical_symbol_name(value: str) -> str:
    return re.sub(r"[^A-Za-z]", "", value or "").upper()


def trendbar_to_candle(trendbar: Any, digits: int) -> Candle:
    low_relative = int(getattr(trendbar, "low", 0) or 0)
    scale = 100000.0
    low = round(low_relative / scale, digits)
    open_price = round((low_relative + int(getattr(trendbar, "deltaOpen", 0) or 0)) / scale, digits)
    high = round((low_relative + int(getattr(trendbar, "deltaHigh", 0) or 0)) / scale, digits)
    close = round((low_relative + int(getattr(trendbar, "deltaClose", 0) or 0)) / scale, digits)
    timestamp = int(getattr(trendbar, "utcTimestampInMinutes", 0) or 0) * 60
    if timestamp <= 0:
        raise ValueError("cTrader trendbar is missing utcTimestampInMinutes")
    return Candle(time=timestamp, open=open_price, high=high, low=low, close=close)


def choose_authorized_account(
    accounts: Iterable[Any],
    *,
    account_id: int,
    environment: str,
    broker_hint: str = "ICMarkets",
) -> Any:
    rows = tuple(accounts)
    if account_id <= 0:
        raise RuntimeError("OAK_CTRADER_ACCOUNT_ID is required; auto-picking an account is disabled")
    chosen = next(
        (row for row in rows if int(getattr(row, "ctidTraderAccountId", 0) or 0) == account_id),
        None,
    )
    if chosen is None:
        raise RuntimeError(f"cTrader account {account_id} is not authorised for this access token")
    expected_live = environment == "live"
    actual_live = bool(getattr(chosen, "isLive", False))
    if actual_live != expected_live:
        raise RuntimeError(
            f"cTrader account environment mismatch: expected {environment}, "
            f"account is {'live' if actual_live else 'demo'}"
        )
    broker_title = str(getattr(chosen, "brokerTitleShort", "") or "")
    hint = canonical_symbol_name(broker_hint)
    normalized_broker = canonical_symbol_name(broker_title)
    if hint and broker_title and hint not in normalized_broker and normalized_broker not in hint:
        raise RuntimeError(
            f"cTrader broker mismatch: expected {broker_hint!r}, authorised account reports {broker_title!r}"
        )
    return chosen


def resolve_light_symbols(light_symbols: Iterable[Any], requested: Sequence[str]) -> dict[str, Any]:
    by_name = {
        canonical_symbol_name(str(getattr(row, "symbolName", "") or "")): row
        for row in light_symbols
    }
    resolved: dict[str, Any] = {}
    for base in requested:
        key = canonical_symbol_name(base)
        row = by_name.get(key)
        if row is None:
            raise RuntimeError(f"cTrader symbol not found: {base}")
        resolved[key] = row
    return resolved


def _extract_message(protobuf: Any, message: Any) -> Any:
    try:
        return protobuf.extract(message)
    except Exception:
        return message


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
