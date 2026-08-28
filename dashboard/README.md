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

Current public schema: v15. Cloud state is v53 and signal-rule version is v47.

The H1 engine routes `H3` to the four FX targets (`GBPUSD/AUDUSD/USDCAD/USDJPY`), `H4` to `XAUUSD` only, and `H6/H9/H12/H14/H16` to all five targets. All six pattern classifiers and their entry-time offsets remain intact: P1/P2/P5 enter at `H+2:00`; P3/P4 enter at `H+1:25`; P6 uses pattern candles 5-6 to choose `H+2:00` for `TG/GT` or `H+1:25` for `TT/GG`. Signal direction is calculated independently at the exact entry M5 candle from its Open versus Bollinger Middle(20), period 20 / shift 0 / applied Close. Historical evaluation substitutes the current entry Open for the still-unclosed current Close and uses the prior 19 closed M5 Closes, preventing look-ahead. Above Middle maps XAUUSD/AUDUSD to BUY and GBPUSD/USDCAD/USDJPY to SELL; below Middle maps the opposite. Equal, missing, non-finite or incomplete M5 evidence yields no alert. The monthly weekday phase anchored by the first Thursday applies to all five symbols: cycle months reverse Fri/Tue and keep Thu/Mon/Wed; regular months reverse Thu/Mon/Wed and keep Fri/Tue. AUDUSD Tuesday and GBPUSD Thursday each toggle once more, using XOR so two reversals cancel. The table and PNG highlight each symbol row only when its final net post-signal state is reversed.

Cloudflare is the primary phase scheduler. H:00 evaluates newly available `:00` entry M5 evidence, while H:30 evaluates the `:25` entry M5 candle after its Open exists; H:01/H:15/H:30 plus the minute watchdog heal delayed provider candles, and GitHub supplies the phase-aware fallback. Signal evaluation remains active through H18 so the H16 block can finish. On a live eligible signal, the scanner creates one idempotent cTrader intent for the exact enabled scanner account with fixed lot `0.03` and status `approval_required`. Telegram shows the intent ID, BUY/SELL, symbol, entry time, account and `/approve ID`. The scanner route does not approve or execute the intent; broker execution remains impossible until the operator explicitly approves it.

The H1 feed retains broker-date records inside the latest 90 calendar days relative to the newest valid stored broker date. `/engine` defaults to the newest date and can filter retained dates by Monday-Friday. Mobile intentionally continues to consume only the latest retained date.

Run locally:

```bash
npm ci
npm run test
npm run build
```
