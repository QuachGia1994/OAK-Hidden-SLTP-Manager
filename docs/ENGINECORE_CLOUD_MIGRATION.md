# OAK EngineCore Cloud Migration

## Goal

Move Engine5 market data, Telegram distribution, and eventually order/SL/TP management off the local PC without changing Pattern5 semantics.

Production remains MT5 until every cloud-data gate below passes. The migration is deliberately shadow-first and fail-closed.

## Non-negotiable parity rule

Engine5 depends on broker H4 candle boundaries. A cloud provider is not allowed to drive production merely because its prices look similar.

Before cutover, for GBPUSD and EURUSD it must pass:

1. exact broker-day offset parity;
2. exact H4 open timestamps;
3. OHLC within configured quote tolerance;
4. therefore identical Pattern5 group (`Sr`/`Sw`/`Bt`), base signal, reverse flag and final signal for the shadow window.

Any mismatch is fail-closed: MT5 remains the production source.

## Provider contract v1

`robot-sltp-pro/market_data_provider.py` defines the canonical provider interface:

- `symbols()`
- `broker_day_offset(symbol)`
- `h4_range(symbol, start_epoch, end_epoch)`
- `warm_h4(symbol)`

`MT5MarketDataProvider` is the compatibility baseline.
`SnapshotMarketDataProvider` is the deterministic cloud/replay contract.

`pattern5_engine.render_profile_with_provider()` can run Pattern5 without initializing MT5 when a non-MT5 provider is supplied.

## Parity gate

`market_data_parity.py` compares broker-day offset, candle timestamps and OHLC.
`market_data_parity_cli.py` compares two JSON snapshots and exits non-zero on mismatch.

A candidate source must remain shadow-only until the parity gate passes.

## IC Markets cloud path: cTrader Open API

The implementation uses the official Spotware Python SDK in an isolated one-shot process. Twisted is not embedded into the long-lived Tauri/MT5 worker.

Files:

- `ctrader_market_data.py` — canonical symbol mapping, cTrader trendbar conversion, exact account fencing and one-shot collector.
- `ctrader_snapshot_cli.py` — fetch IC Markets cTrader H1 and write an MT5-boundary H4 snapshot.
- `ctrader_accounts_cli.py` — list authorised cTrader account IDs safely after OAuth.
- `mt5_snapshot_cli.py` — export the IC Markets/Vantage MT5 baseline for parity.
- `ctrader_cloud_config.py` — direct-env or Vercel control-plane session config.

The official SDK dependency is pinned in `requirements.txt` as `ctrader-open-api==0.9.2`.

### cTrader bar conversion and MT5 boundary reconstruction

The collector uses the Open API H1 trendbar fields directly:

- candle open time = `utcTimestampInMinutes * 60`;
- low = `low / 100000`;
- open/high/close = `(low + delta*) / 100000`, rounded to cTrader symbol digits.

Raw cTrader H4 is **not** used as the parity candidate. IC MetaTrader charts use a New-York-close server clock: UTC+2 in US standard time and UTC+3 while New York is on daylight saving time. cTrader trendbar timestamps are UTC, so direct platform H4 boundaries are not assumed to match.

OAK therefore fetches cTrader H1 and reconstructs H4 on the IC MetaTrader boundary:

- winter broker midnight: 22:00 UTC;
- summer broker midnight: 21:00 UTC;
- H4 starts satisfy `(utc_epoch + mt5_server_offset) % 14400 == 0`;
- each output H4 requires four consecutive H1 candles;
- open = first H1 open, high = max H1 high, low = min H1 low, close = fourth H1 close;
- incomplete or DST-crossing four-hour groups are skipped rather than fabricated.

The offset is calculated with the `America/New_York` IANA timezone, so US DST transitions are not hard-coded by calendar date. The resulting broker-day offset is then compared against the current IC MT5 baseline before Engine5 cutover.

## OAuth and token vault on Vercel

Production callback URI:

`https://www.oakgatekeeper.uk/api/ctrader/oauth`

The first migration stage requests only cTrader OAuth scope `accounts`. Trading scope is intentionally not requested yet.

Server routes:

- `POST /api/ctrader/oauth` — requires `x-api-key: DASHBOARD_API_KEY`; creates a one-time 10-minute onboarding ticket.
- `GET /api/ctrader/oauth?ticket=...` — consumes the one-time ticket and redirects to the cTrader authorisation screen.
- `GET /api/ctrader/oauth?code=...` — exchanges the short-lived authorisation code and stores tokens.
- `GET /api/ctrader/status` — safe readiness/status only, including `vaultKeyConfigured`; never exposes credentials/token/account ID or vault material.
- `GET /api/ctrader/session` — service-to-service only, requires `x-api-key`; returns a short-lived current access session to a cloud collector and never returns the refresh token.
- `GET /api/ctrader/session?discovery=1` — same private endpoint but allows account discovery before an account ID is selected. It accepts the normal `x-api-key` auth or a short-lived one-time `x-ctrader-session-ticket` bootstrap header that is consumed atomically; the refresh token is never returned.

### Vault security

The access/refresh token payload is encrypted with AES-256-GCM before it is written to Upstash Redis.

Encryption material:

- `OAK_CTRADER_VAULT_KEY` is mandatory for every new/updated vault write and must be an independent high-entropy secret.
- `DASHBOARD_API_KEY` is authentication material, not a write key. It is accepted only to decrypt a legacy vault record created before the dedicated-key requirement; when the dedicated key is present that record is immediately re-encrypted with `OAK_CTRADER_VAULT_KEY`.

No plaintext access token, refresh token or client secret is written to public Redis, browser JS, Git, `profiles.json` or status responses.

The Vercel vault refreshes the cTrader access token before expiry. The refresh token stays inside the encrypted server vault.

## Required cTrader application settings

Create/approve one cTrader Open API application and set this redirect URI in the Open API portal:

`https://www.oakgatekeeper.uk/api/ctrader/oauth`

Production server environment variables:

- `OAK_CTRADER_CLIENT_ID`
- `OAK_CTRADER_CLIENT_SECRET`
- `OAK_CTRADER_REDIRECT_URI=https://www.oakgatekeeper.uk/api/ctrader/oauth`
- `OAK_CTRADER_ENV=demo` for the first parity phase
- `OAK_CTRADER_BROKER=ICMarkets`
- `OAK_CTRADER_ACCOUNT_ID=<ctidTraderAccountId>` after discovery
- `OAK_CTRADER_VAULT_KEY=<independent high-entropy secret>`

A remote collector can avoid storing broker tokens by using:

- `OAK_CTRADER_SESSION_URL=https://www.oakgatekeeper.uk/api/ctrader/session`
- `DASHBOARD_API_KEY=<server-to-server key>`

The collector receives the current access token in memory only. Token refresh remains on Vercel.

## Account discovery after OAuth

The OAuth token authorises one or more cTrader accounts but does not replace `ctidTraderAccountId` in protocol requests.

After OAuth, run the account discovery collector against the private control-plane session. It prints only:

- `accountId`
- UI trader login
- demo/live environment
- broker display name

Select the IC Markets demo account and set its `accountId` as `OAK_CTRADER_ACCOUNT_ID`. Market-data collection fails closed if account ID, environment or broker does not match.

## Shadow parity commands

### 1. Export current IC Markets MT5 baseline

This is the only step that still needs the local/VPS MT5 terminal during migration:

`python robot-sltp-pro/mt5_snapshot_cli.py --profile ICMarkets --days 21 --output ic_mt5.json`

### 2. Fetch IC Markets cTrader candidate

Using direct credentials or the Vercel session endpoint:

`python robot-sltp-pro/ctrader_snapshot_cli.py --days 21 --output ic_ctrader.json`

### 3. Run fail-closed parity

`python robot-sltp-pro/market_data_parity_cli.py ic_mt5.json ic_ctrader.json`

The candidate is not allowed to publish production Engine5 until the agreed multi-day shadow window is clean.

## Vantage path

Keep Vantage MT5 as baseline until a broker-supported programmable API is confirmed and tested. Do not automate through undocumented TradingView/private endpoints.

The provider abstraction allows a future official Vantage adapter without changing Pattern5 core.

## Execution migration after market-data parity

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

Trading OAuth scope is a separate future gate. The initial cTrader onboarding uses `accounts` scope only and cannot place trades.

## Current status / STOP GATE — 2026-08-18

Repository and Vercel control-plane preparation are complete for the read-only market-data phase.

Current state:

- cTrader Open API application created and submitted to Spotware;
- redirect URI registered as `https://www.oakgatekeeper.uk/api/ctrader/oauth`;
- Vercel cTrader client configuration and encrypted vault configuration are present and redeployed;
- production status route confirms the app/vault layer is configured without exposing secrets;
- requested OAuth scope remains `accounts` only;
- no cTrader account has been authorised/discovered yet;
- production Engine 5 source remains MT5 and cloud data remains shadow-only.

The remaining blocker is **Spotware application activation/KYC**. The portal must move the application from Submitted to Active before the OAuth/token/account-discovery flow can run.

After the application becomes Active:

1. rotate any onboarding credential that may have been exposed during setup and update Vercel directly;
2. authorise the IC Markets **demo** cTrader account with `accounts` scope;
3. run account discovery and set the verified `ctidTraderAccountId`;
4. export the MT5 baseline snapshot;
5. collect cTrader H1 and reconstruct MT5-aligned H4;
6. run multi-day timestamp/OHLC parity;
7. compare Engine 5 group/base/reverse/final signals;
8. keep production on MT5 unless every parity gate passes.

Trading scope/order execution remains a separate later gate and is intentionally not enabled by this phase.
