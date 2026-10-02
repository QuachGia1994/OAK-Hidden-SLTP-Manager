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

Current public schema remains v18. Cloud state remains schema-stable v56 and the fixed-entry contract is signal-rule version v102.

H1 rule v102 is fixed-entry-only across exactly six blocks (`H3/H4/H7/H11/H14/H16`). Each block header carries its fixed times: SELL = `07:25 / 08:25 / 08:49 / 15:49 / 18:49 / 20:49`; BUY = `03:35 / 04:35 / 09:35 / 12:35 / 15:35 / 17:35`. The table body is the operator-owned weekday C/N sheet (`H1_WEEKDAY_PATTERNS` in `src/lib/h1-entry-schedule.ts`; C = Cùng/same, N = Ngược/opposite) in two groups, Normal and SW, rows Thu → Fri → Mon → Tue → Wed with a note column; the selected broker date's weekday row is highlighted. Candle, pattern, reversal and derived BUY/SELL calculation are intentionally removed until a new signal rule is implemented.

Automatic H1 scanner/backfill scheduling is disabled. `/api/h1-scanner/local-market` validates provenance but returns `calculationDisabled: true`, and the GitHub H1 workflow is manual-only. Timed Telegram entry commands remain an independent operator-owned broker-execution path; they no longer depend on candle/pattern scanner output.

The H1 UI synthesizes a 90-calendar-day weekday history shell for date navigation. Every retained weekday renders the same fixed weekday C/N table, highlighting that date's weekday row; no historical candle reconstruction or signal backfill is performed, so history reflects a table change on the next deploy without a rebuild step.

Run locally:

```bash
npm ci
npm run test
npm run build
```
