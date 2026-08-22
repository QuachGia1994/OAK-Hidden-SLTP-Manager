# ROBOT SLTP / OAK Gatekeeper

Production repository for the OAK web control plane and the standalone MT5 EA.

The repository was intentionally trimmed on 2026-08-22 to remove the legacy desktop/Tauri application, local Python worker/fallback runtime, local H1 scanner, root Python test suite, and obsolete runtime utilities.

## Production surfaces

- `dashboard/` — Next.js web/control plane deployed on Vercel. Owns `/engine`, `/accounts`, Telegram cloud control, cTrader integration, H1 cloud scanner, Fact Check, Tarot, Redis state and the MT5 outbound mailbox.
- `cloudflare/h1-timekeeper/` — Cloudflare Durable Object/Cron timekeeper for H1 scanner triggering.
- `services/media-forensics/` — optional web-side media-forensics service used by Fact Check when configured.
- `mt5/OAK_Cloud_Manager_EA.mq5` — standalone MQL5 execution/account-management runtime attached directly to each controlled MT5 terminal.
- `.github/workflows/` — web CI plus H1/Telegram cloud fallback schedulers.

## Runtime flow

```text
Telegram / web schedule
        |
        v
Vercel control plane -> Upstash mailbox -> OAK_Cloud_Manager_EA -> MT5 broker

cTrader H1 market data -> Vercel H1 scanner -> Upstash public feed -> /engine + Telegram
                         ^
                         |
              Cloudflare H1 timekeeper
```

There is no maintained desktop/Tauri runtime and no local Python broker worker in this repository. MT5 execution is owned by the EA; cloud orchestration is owned by the web control plane.

## Web development

```bash
cd dashboard
npm ci
npm test
npm run build
```

Cloudflare timekeeper tests:

```bash
cd cloudflare/h1-timekeeper
npm test
```

Vercel project configuration lives in `dashboard/vercel.json` and the local `.vercel/` link metadata.

## MT5 EA

See `mt5/README.md` for installation, WebRequest permission, account binding and Upstash bridge configuration. The EA source of truth is:

`mt5/OAK_Cloud_Manager_EA.mq5`

Never commit populated MT5 `.set` files, Upstash tokens, broker credentials or Vercel secrets.
