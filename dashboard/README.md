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
