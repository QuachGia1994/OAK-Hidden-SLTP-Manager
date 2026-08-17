# OAK EngineCore Cloud Migration

## Goal

Move Engine5 market data, Telegram distribution, and eventually order/SL/TP management off the local PC without changing Pattern5 semantics.

## Non-negotiable parity rule

Engine5 depends on broker H4 candle boundaries. A cloud provider is not allowed to drive production merely because its prices look similar.

Before cutover, for GBPUSD and EURUSD it must pass:

1. exact broker-day offset parity;
2. exact H4 open timestamps;
3. OHLC within configured quote tolerance;
4. identical Pattern5 group (`Sw`/`Bt`), base signal, reverse flag and final signal for the shadow window.

Any mismatch is fail-closed: MT5 remains the production source.

## Provider contract v1

`robot-sltp-pro/market_data_provider.py` defines the canonical provider interface:

- `symbols()`
- `broker_day_offset(symbol)`
- `h4_range(symbol, start_epoch, end_epoch)`
- `warm_h4(symbol)`

`MT5MarketDataProvider` is the compatibility baseline.
`SnapshotMarketDataProvider` is the deterministic cloud/replay contract.

`pattern5_engine.render_profile_with_provider()` can now run Pattern5 without initializing MT5 when a non-MT5 provider is supplied.

## Parity gate

`market_data_parity.py` compares broker-day offset, candle timestamps and OHLC.
`market_data_parity_cli.py` compares two JSON snapshots and exits non-zero on mismatch.

A candidate source must remain shadow-only until the parity gate passes.

## IC Markets path

Primary cloud candidate: cTrader Open API.

Environment variables reserved for the adapter:

- `OAK_CTRADER_CLIENT_ID`
- `OAK_CTRADER_CLIENT_SECRET`
- `OAK_CTRADER_ACCESS_TOKEN`
- `OAK_CTRADER_REFRESH_TOKEN`
- `OAK_CTRADER_ACCOUNT_ID`
- `OAK_CTRADER_ENV=demo|live`
- `OAK_CTRADER_BROKER=ICMarkets`

Secrets must stay in the server secret store/environment; never in `profiles.json`, Git, browser JS or public Redis.

Development sequence:

1. Register/approve an Open API application.
2. OAuth with `accounts` scope first.
3. Pull IC Markets H4 trendbars in shadow mode.
4. Compare against the current IC Markets MT5 feed for GBPUSD/EURUSD.
5. Require a multi-day clean parity window before switching Engine5 market data.
6. Only after data cutover, request/use `trading` scope for cloud order management.

## Vantage path

Keep Vantage MT5 as baseline until a broker-supported programmable API is confirmed and tested. Do not automate through undocumented TradingView/private endpoints.

The provider abstraction allows a future official Vantage adapter without changing Pattern5 core.

## Execution migration

Market-data independence and execution independence are separate gates.

Target layers:

1. Cloud Market Data
2. Engine5 Signal Core
3. Upstash/Web Publisher
4. Subscriber Entitlement
5. Telegram Distributor
6. Broker Execution Adapter
7. Position/SL/TP/BE/partial-close state machine

For execution adapters, preserve the current safety properties:

- account identity fencing;
- idempotency keys;
- reconciliation after unknown broker outcomes;
- no blind retry after ambiguous execution;
- per-account risk gate;
- server-side secret storage;
- audit trail for every mutation.

## Stop gate for the next stage

IC Markets cTrader live integration cannot be exercised until the Open API application credentials and an authorised cTrader account are available. Until then, production remains MT5 and the cloud provider stays shadow-only.
