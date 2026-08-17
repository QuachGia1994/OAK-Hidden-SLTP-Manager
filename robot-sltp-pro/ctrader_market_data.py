from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo

from ctrader_cloud_config import CTraderCloudConfig
from market_data_provider import Candle, SnapshotMarketDataProvider


DEFAULT_SYMBOLS = ("GBPUSD", "EURUSD")
NEW_YORK_TZ = ZoneInfo("America/New_York")
H4_SECONDS = 4 * 3600


def canonical_symbol_name(value: str) -> str:
    """Normalize broker display names such as ``EUR/USD`` to Engine5 form."""

    return re.sub(r"[^A-Za-z]", "", value or "").upper()


def trendbar_to_candle(trendbar: Any, digits: int) -> Candle:
    """Convert cTrader relative-price trendbar to the Engine5 candle contract."""

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


def mt5_new_york_close_offset_seconds(epoch: int) -> int:
    """IC MetaTrader offset: UTC+2 standard, UTC+3 while New York is on DST."""

    instant = datetime.fromtimestamp(int(epoch), tz=timezone.utc).astimezone(NEW_YORK_TZ)
    daylight = instant.dst() or timedelta(0)
    return 3 * 3600 if daylight != timedelta(0) else 2 * 3600


def mt5_broker_day_offset(epoch: int) -> int:
    """UTC epoch remainder of broker midnight (21:00/22:00 UTC)."""

    return (86400 - mt5_new_york_close_offset_seconds(epoch)) % 86400


def rebucket_h1_to_mt5_h4(candles: Sequence[Candle]) -> tuple[Candle, ...]:
    """Aggregate UTC cTrader H1 bars into IC MetaTrader New-York-close H4 bars.

    Only complete groups of four consecutive hourly bars are emitted. This is
    deliberately strict: missing hours or a DST boundary inside a group are
    skipped rather than fabricated.
    """

    by_time = {int(candle.time): candle for candle in candles}
    output: list[Candle] = []
    for timestamp in sorted(by_time):
        offset = mt5_new_york_close_offset_seconds(timestamp)
        if (timestamp + offset) % H4_SECONDS != 0:
            continue
        expected = [timestamp + index * 3600 for index in range(4)]
        if any(item not in by_time for item in expected):
            continue
        group = [by_time[item] for item in expected]
        if any(mt5_new_york_close_offset_seconds(item) != offset for item in expected):
            continue
        output.append(
            Candle(
                time=timestamp,
                open=group[0].open,
                high=max(item.high for item in group),
                low=min(item.low for item in group),
                close=group[-1].close,
            )
        )
    return tuple(output)


def choose_authorized_account(
    accounts: Iterable[Any],
    *,
    account_id: int,
    environment: str,
    broker_hint: str = "ICMarkets",
) -> Any:
    """Resolve the exact account and fail closed on environment/broker mismatch."""

    rows = tuple(accounts)
    if account_id <= 0:
        raise RuntimeError("OAK_CTRADER_ACCOUNT_ID is required; auto-picking a trading account is disabled")
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


def snapshot_from_ctrader_rows(
    *,
    provider_id: str,
    symbols: dict[str, tuple[int, Sequence[Any]]],
    h1_bars: dict[str, Sequence[Any]],
    as_of_epoch: int,
) -> SnapshotMarketDataProvider:
    """Build MT5-aligned H4 candles from raw cTrader UTC H1 trendbars."""

    candles_by_symbol: dict[str, tuple[Candle, ...]] = {}
    day_offsets: dict[str, int] = {}
    for symbol, (_symbol_id, full_symbols) in symbols.items():
        full = next(iter(full_symbols), None)
        if full is None:
            raise RuntimeError(f"Missing full cTrader symbol metadata for {symbol}")
        digits = int(getattr(full, "digits", 5) or 5)
        converted_h1 = tuple(
            sorted(
                (trendbar_to_candle(row, digits) for row in h1_bars.get(symbol, ())),
                key=lambda candle: candle.time,
            )
        )
        if not converted_h1:
            raise RuntimeError(f"No H1 trendbars returned for {symbol}")
        rebucketed = rebucket_h1_to_mt5_h4(converted_h1)
        if not rebucketed:
            raise RuntimeError(f"No complete MT5-aligned H4 candles could be built for {symbol}")
        candles_by_symbol[symbol] = rebucketed
        day_offsets[symbol] = mt5_broker_day_offset(as_of_epoch)

    return SnapshotMarketDataProvider(provider_id, candles_by_symbol, day_offsets)


@dataclass(frozen=True, slots=True)
class CTraderSnapshotResult:
    provider: SnapshotMarketDataProvider
    account_id: int
    environment: str
    broker: str
    server_offset_seconds: int

    def as_payload(self) -> dict[str, object]:
        payload = self.provider.as_payload()
        payload["metadata"] = {
            "accountId": self.account_id,
            "environment": self.environment,
            "broker": self.broker,
            "source": "ctrader-open-api",
            "rebucketMode": "mt5-new-york-close-from-h1",
            "serverOffsetSeconds": self.server_offset_seconds,
        }
        return payload


def _extract_message(protobuf: Any, message: Any) -> Any:
    try:
        return protobuf.extract(message)
    except Exception:
        return message


def collect_snapshot_deferred(
    reactor: Any,
    config: CTraderCloudConfig,
    *,
    symbols: Sequence[str] = DEFAULT_SYMBOLS,
    start_epoch: int,
    end_epoch: int,
):
    """Connect once, authenticate, fetch metadata + H1, then disconnect.

    Imports are intentionally local so the rest of ROBOT SLTP can run without
    importing Twisted/cTrader SDK unless this isolated cloud collector is used.
    """

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

    host = (
        EndPoints.PROTOBUF_LIVE_HOST
        if config.environment == "live"
        else EndPoints.PROTOBUF_DEMO_HOST
    )
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

            symbol_meta: dict[str, tuple[int, Sequence[Any]]] = {}
            h1_rows: dict[str, Sequence[Any]] = {}
            h1_start = max(0, start_epoch - 6 * 3600)

            for base in symbols:
                canonical = canonical_symbol_name(base)
                symbol_id = int(getattr(light[canonical], "symbolId"))
                full_symbol = full_by_id.get(symbol_id)
                if full_symbol is None:
                    raise RuntimeError(f"Full cTrader symbol metadata missing: {canonical}")
                symbol_meta[canonical] = (symbol_id, (full_symbol,))

                h1_req = ProtoOAGetTrendbarsReq()
                h1_req.ctidTraderAccountId = account_id
                h1_req.symbolId = symbol_id
                h1_req.period = ProtoOATrendbarPeriod.Value("H1")
                h1_req.fromTimestamp = h1_start * 1000
                h1_req.toTimestamp = end_epoch * 1000
                h1_raw = yield client.send(h1_req)
                h1_response = _extract_message(Protobuf, h1_raw)
                h1_rows[canonical] = tuple(getattr(h1_response, "trendbar", ()))

            provider_id = (
                f"ctrader-open-api-mt5-h4:{canonical_symbol_name(config.broker)}:"
                f"{config.environment}:{account_id}"
            )
            provider = snapshot_from_ctrader_rows(
                provider_id=provider_id,
                symbols=symbol_meta,
                h1_bars=h1_rows,
                as_of_epoch=end_epoch,
            )
            return CTraderSnapshotResult(
                provider=provider,
                account_id=account_id,
                environment=config.environment,
                broker=config.broker,
                server_offset_seconds=mt5_new_york_close_offset_seconds(end_epoch),
            )
        finally:
            try:
                client.stopService()
            except Exception:
                pass

    return run()
