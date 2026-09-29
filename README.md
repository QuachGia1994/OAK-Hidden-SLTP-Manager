# ROBOT SLTP / OAK Gatekeeper

Production repository for the OAK web control plane and standalone MT5 EA.

The legacy desktop/Tauri application remains retired. The repository also carries a maintained PC-local failover runtime for Telegram control alongside the cloud control plane.

## Production surfaces

- `dashboard/` — Next.js web/control plane deployed on Vercel. Owns `/engine`, `/accounts`, Telegram cloud control, cTrader integration, the fixed H1 entry schedule, Fact Check, Tarot, Redis state and the MT5 outbound mailbox.
- `cloudflare/h1-timekeeper/` — retained Cloudflare timekeeper compatibility surface; H1 BUY/SELL calculation is currently disabled.
- `services/media-forensics/` — optional web-side media-forensics service used by Fact Check when configured.
- `mt5/OAK_Cloud_Manager_EA.mq5` — standalone MQL5 execution/account-management runtime attached directly to each controlled MT5 terminal.
- `mt5/OAK_NeoTech_Compliance_EA.mq5` — optional, read-only C5 helper. v1.09 works standalone with a local C5 popup and chart `C5 LOOK`, auto-binds the active MT5 login/server across account switches, and can optionally forward the same reminder/`/look` through an already-provisioned OAK Local Telegram controller. The 14-rule assessment remains in the separate ReadOnly Connector/dashboard. `/neotech` publishes a one-click Windows Setup, direct EX5, checksums and guide.
- `local-failover/` — maintained PC-local Telegram failover. H1 market-data calculation is disabled; the retained H1 helper is diagnostic-only while the web uses the fixed entry schedule.
- `.github/workflows/` — web CI plus H1/Telegram cloud fallback workflows.

## Runtime flow

```text
Telegram / web schedule
        |
        v
Vercel control plane -> Upstash mailbox -> OAK_Cloud_Manager_EA -> MT5 broker

Fixed H1 entry schedule -------------------------------> /engine

Telegram / local-failover -> scheduled broker intents -> MT5
```

There is no maintained desktop, Android, iOS, or Expo client. The product UI is web-only. MT5 trade execution is owned by the EA; cloud orchestration is owned by the web control plane, while `local-failover/` provides PC-local Telegram failover and does not replace the EA as trade executor.

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

See `mt5/README.md` for MT5 setup documentation. The independent NeoTech compliance source is `mt5/OAK_NeoTech_Compliance_EA.mq5` plus `mt5/neotech/`.

The NeoTech surface is unofficial/advisory and does not grant or claim NeoTech approval. Its backend validates transport/schema and renders stored MQL5 conclusions; it does not implement a second TypeScript compliance engine.

Never commit populated MT5 `.set` files, Upstash tokens, compliance ingest keys, broker credentials or Vercel secrets.