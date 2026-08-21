# OAK Gatekeeper Dashboard

Next.js production web/control plane for ROBOT SLTP.

Trading surface:

- `/engine` — H1 cloud scanner only; profile is sourced from the H1 feed (`cTrader IcMarkets`).
- `/api/h1-scanner/run` — private cTrader H1 scanner invocation.
- `/api/h1-scanner/setup` — one-time encrypted scanner/Telegram config bootstrap.
- `/api/telegram/setup` — one-time Telegram webhook bootstrap.
- `/api/telegram/webhook` — primary Telegram cloud receiver.
- `/api/telegram/tick` — OIDC-authenticated due-intent notification tick.
- `/api/ctrader/*` — cTrader OAuth/status/session control plane.

The retired Engine5/Pattern5 H4 feed and UI are no longer part of this dashboard.

H1 public feed key:

`robot-sltp:public:h1-signals:latest`

Current public schema: v3.

Run locally:

```bash
npm ci
npm run test
npm run build
```
