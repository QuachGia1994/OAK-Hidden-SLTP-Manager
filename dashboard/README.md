# OAK Gatekeeper Dashboard

Next.js production web/control plane for ROBOT SLTP.

Trading surface:

- `/engine` — H1 cloud scanner only; profile is sourced from the H1 feed (`cTrader IcMarkets`).
- `/api/h1-scanner/run` — private cTrader H1 scanner invocation.
- `/api/h1-scanner/backfill` — manual admin/API-authenticated reconstruction of the fixed 90-calendar-day H1 history window; it shares the scanner lock and does not send Telegram messages or broker mutations.
- `/api/h1-scanner/setup` — one-time encrypted scanner/Telegram config bootstrap.
- `/api/telegram/setup` — one-time Telegram webhook bootstrap.
- `/api/telegram/webhook` — primary Telegram cloud receiver.
- `/api/telegram/tick` — OIDC-authenticated due-intent notification tick.
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

Current public schema: v14. Cloud state is v52 and signal-rule version is v46.

The H1 engine routes `H3` to the four FX targets (`GBPUSD/AUDUSD/USDCAD/USDJPY`), `H4` to `XAUUSD` only, and `H6/H9/H12/H14/H16` to all five targets. Pattern classification remains separate from signal direction. P1/P2/P5 enter at `H+2:00`; P3/P4 enter at `H+1:25`; P6 uses its pattern candles 5-6 to choose `H+2:00` for `TG/GT` or `H+1:25` for `TT/GG`. For a `:00` entry the signal pair is M15 `entry-15` then `entry-30`; for a `:25` entry it is `entry-25` then `entry-40`. A same-direction pair keeps candle 1, while `TG/GT` reverses candle 1. Pattern 5 retains precedence when a same-direction run reaches at least four candles. After the M15 result, XAUUSD alone uses a monthly weekday phase anchored by the month's first Thursday. If that first Thursday is a cycle Thursday, XAU keeps Thu/Mon/Wed and reverses Fri/Tue; otherwise XAU reverses Thu/Mon/Wed and keeps Fri/Tue. The phase repeats across later weeks, and only dates with an actual XAU reversal color the XAU row. GBPUSD still reverses only on Thursday, AUDUSD only on Tuesday, and USDCAD/USDJPY have no weekday post-signal inversion.

Cloudflare is the primary phase scheduler. H:00 evaluates newly closed `:00` signal pairs, H:15 evaluates the pair needed for `:25` entries, and H:01/H:30 plus the minute watchdog heal delayed provider candles; GitHub supplies the phase-aware fallback. Signal refinement remains active through H18 so the H16 block can finish. On a live eligible signal, the scanner creates one idempotent cTrader intent for the exact enabled scanner account with fixed lot `0.03` and status `approval_required`. Telegram shows the intent ID, BUY/SELL, symbol, entry time, account and `/approve ID`. The scanner route does not approve or execute the intent; broker execution remains impossible until the operator explicitly approves it.

The H1 feed retains broker-date records inside the latest 90 calendar days relative to the newest valid stored broker date. `/engine` defaults to the newest date and can filter retained dates by Monday-Friday. Mobile intentionally continues to consume only the latest retained date.

Run locally:

```bash
npm ci
npm run test
npm run build
```
