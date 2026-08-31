# OAK Gatekeeper Dashboard

Next.js production web/control plane for ROBOT SLTP.

Trading surface:

- `/engine` — H1 cloud scanner only; profile is sourced from the H1 feed (`cTrader IcMarkets`).
- `/api/h1-scanner/run` — private cTrader H1 scanner invocation.
- `/api/h1-scanner/backfill` — manual admin/API-authenticated reconstruction of the fixed 90-calendar-day H1 history window; it shares the scanner lock and does not send Telegram messages or broker mutations.
- `/api/h1-scanner/setup` — one-time encrypted scanner/Telegram config bootstrap.
- `/api/telegram/setup` — one-time Telegram webhook bootstrap.
- `/api/telegram/webhook` — primary Telegram cloud receiver.
- `/api/telegram/tick` — authenticated due-intent execution/expiry tick.
- `/api/ctrader/*` — cTrader OAuth/status/session control plane.

The retired Engine5/Pattern5 H4 feed and UI are no longer part of this dashboard.

NeoTech customer analytics:

- `/neotech` — private browser workspace for customer-owned NeoTech visual profiles.
- `/api/neotech/public/session|pairing|accounts` — tenant-scoped session, one-time pairing, list/revoke/purge APIs.
- `/api/neotech/connector/pair|ingest` — telemetry-only MT5 connector boundary. Investor/read-only is the default. A trading-capable (Master Password) terminal is accepted only when the browser-created one-time pairing explicitly records `TRADING_CAPABLE_ACCEPTED`; the password itself is never sent to OAK.
- `public/downloads/OAK_NeoTech_ReadOnly_Connector.ex5` — compiled connector for low-friction install; the matching `.mq5` source is published beside it for audit.
- The website never requests or stores MT5 Master/Investor passwords. Investor Password is recommended; Master Password is optional only after an explicit risk warning/acceptance. Connector bearer tokens are random 256-bit values and only their SHA-256 hashes are retained server-side.
- Raw deal/cashflow payloads are processed transiently to compute server-authoritative rule results; retained state is limited to masked/fingerprinted account metadata, derived profile, bounded equity samples and security audit metadata. Active retained keys expire after at most 400 days unless refreshed, and the UI offers immediate account-data purge.
- Public NeoTech source is statically contract-tested against imports of MT5/cTrader/Telegram execution surfaces. The MQL5 connector is contract-tested to contain no `CTrade`, `OrderSend`, close/modify/delete trade calls.

H1 public feed key:

`robot-sltp:public:h1-signals:latest`

Current public schema: v17. Cloud state is v55 and signal-rule version is v57.

The H1 engine routes `H3` to the four FX targets (`GBPUSD/GBPAUD/GBPCAD/GBPJPY`), `H4` to `XAUUSD` only, and `H6/H9/H12/H14/H16` to all five targets. All Monday-Friday rows now retain the complete six-block schedule; no weekday block is removed. Signals are derived from the block's own closed H1 candle (hour === slotHour); there is no M15 pattern window and no engine-computed entry time — entry/close appointments are set by the user through the Telegram commands. The bullish/bearish direction of that H1 candle maps directly to BUY/SELL for every FX pair and XAUUSD. The cycle-month six-block post-signal matrix is shared by all symbols; blocks are `[H3/H4] [H6] [H9] [H12] [H14] [H16]` and each block decides independently (`N` = inverted post-signal, `C` = keep): Monday `C N N C C C`, Tuesday `N C N C N C`, Wednesday `N C C C N C`, Thursday `N C C N C N`, Friday `N C C N C C`. A non-cycle (regular) month uses the exact inverse of the weekday row. Historical records and the shareable PNG show the H1 base candle.

Cloudflare is the primary H1 timekeeper and GitHub remains a fallback. The H1 scanner is web-only: it persists the closed-candle/matrix state and does not send `BLOCK ĐÃ ĐẾN` or H1 signal Telegram notifications. Timed Telegram entry commands are the operator-owned signal input. When a future `BUY`/`SELL` command is accepted, its Vietnam appointment is converted to the IC Markets broker wall clock and the side is written immediately to the latest eligible H1 cell for that symbol/date; for example `buy XAUUSD 0.01 13h00 @fxce` on 2026-08-31 maps to broker H09 and publishes `BUY` in the XAUUSD H09 cell. Scanner/backfill refreshes preserve that `scheduledSignal`. Broker execution remains governed by the Telegram scheduled-intent path.

The H1 feed retains broker-date records inside the latest 90 calendar days relative to the newest valid stored broker date. `/engine` defaults to the newest date, exposes Monday-Friday filters and a visual native calendar picker constrained to the retained broker-date range. Mobile intentionally continues to consume only the latest retained date.

Run locally:

```bash
npm ci
npm run test
npm run build
```
