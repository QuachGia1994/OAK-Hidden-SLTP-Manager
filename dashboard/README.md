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

Current public schema: v7. Cloud state remains v10 and signal-rule version remains v4.

The H1 feed retains broker-date records inside the latest 90 calendar days relative to the newest valid stored broker date. `/engine` defaults to the newest date and can filter retained dates by Monday-Friday. Mobile intentionally continues to consume only the latest retained date.

Run locally:

```bash
npm ci
npm run test
npm run build
```
