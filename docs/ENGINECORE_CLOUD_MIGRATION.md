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

## IC Markets cTrader path: H1 scanner parity only

The cTrader integration now has a deliberately narrower job: read-only H1 parity for the passive scanner. It is not an Engine5 H4 cutover candidate. Engine5 remains MT5-backed.

The implementation uses the official Spotware Python SDK in an isolated one-shot process. Twisted is not embedded into the long-lived Tauri/MT5 worker.

Files:

- `ctrader_market_data.py` — canonical symbol mapping, cTrader trendbar conversion and exact account fencing retained for compatibility.
- `ctrader_h1_market_data.py` — direct H1 collector for scanner parity; no H4 reconstruction.
- `h1_market_data.py` — current-broker-day H1 snapshot + scanner-semantic parity contract.
- `ctrader_snapshot_cli.py` — fetch the current closed cTrader H1 snapshot.
- `mt5_h1_snapshot_cli.py` — attach-only MT5 closed-H1 baseline snapshot.
- `h1_market_data_parity_cli.py` — compare H1 timestamps and T/G direction; OHLC differences are diagnostic only.
- `ctrader_accounts_cli.py` — list authorised cTrader account IDs safely after OAuth.
- `ctrader_cloud_config.py` — direct-env or Vercel control-plane session config.

The official SDK dependency is pinned in `requirements.txt` as `ctrader-open-api==0.9.2`.

### H1 normalization

The collector uses Open API H1 trendbar fields directly:

- candle open time = `utcTimestampInMinutes * 60`;
- low = `low / 100000`;
- open/high/close = `(low + delta*) / 100000`, rounded to cTrader symbol digits.

For parity only, cTrader UTC H1 opening times are normalized into the same IC Markets MT5 server-wall timestamp encoding (UTC+2 standard / UTC+3 during New-York DST). The candle remains H1; it is never aggregated into H4.

The parity pass/fail rule is intentionally aligned with the scanner: every closed H1 slot for the selected broker day must exist on both sides and its direction must match (`T` when close > open, otherwise `G`). OHLC deltas are still reported for diagnostics but do not decide scanner parity because the scanner does not consume the exact price values.

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

## H1 scanner parity commands

### 1. Export current IC Markets MT5 H1 baseline

This is attach-only and will not start a terminal:

`python robot-sltp-pro/mt5_h1_snapshot_cli.py --profile ICMarkets --output ic_mt5_h1.json`

### 2. Fetch IC Markets cTrader H1 candidate

Using direct credentials or the Vercel session endpoint:

`python robot-sltp-pro/ctrader_snapshot_cli.py --days 2 --output ic_ctrader_h1.json`

### 3. Compare scanner semantics

`python robot-sltp-pro/h1_market_data_parity_cli.py ic_mt5_h1.json ic_ctrader_h1.json`

A PASS means the closed H1 slot set and T/G direction match for the broker day. This parity does not authorize Engine5 market-data cutover or trading execution.

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

## Current status — 2026-08-21

The cTrader application is Active and the read-only OAuth/control-plane path is operational.

Current state:

- production OAuth is authorised with `accounts` scope only;
- the encrypted Vercel/Upstash vault is readable and refresh-capable;
- an IC Markets live account with `NO_TRADING` account access is selected for shadow market-data reads;
- cTrader remains read-only/shadow-only and has no trading OAuth scope;
- production Engine5 remains MT5-backed;
- cTrader is used only for current-broker-day H1 scanner parity;
- the parity contract compares broker-wall H01..H16 slot presence and T/G direction for `GBPUSD`, `XAUUSD`, `EURUSD`, `AUDUSD`, `USDCAD`, and `USDJPY`; OHLC deltas are diagnostic only.

On 2026-08-21 the current broker-day H1 scanner parity passed direction/timestamp parity for all six symbols available at the test time. This does not authorize Engine5 cutover or execution.

Trading scope/order execution remains a separate future gate and is intentionally not enabled.
