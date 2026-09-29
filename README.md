# ROBOT SLTP / OAK Gatekeeper

Production repository for the OAK web control plane, native Android/iOS shell and standalone MT5 EA.

The legacy desktop/Tauri application remains retired. The repository also carries a maintained PC-local failover runtime for Telegram control and ICMarkets H1 market publishing/history backfill alongside the cloud control plane.

## Production surfaces

- `dashboard/` — Next.js web/control plane deployed on Vercel. Owns `/engine`, `/accounts`, Telegram cloud control, cTrader integration, H1 cloud scanner, Fact Check, Tarot, Redis state and the MT5 outbound mailbox.
- `cloudflare/h1-timekeeper/` — Cloudflare Durable Object/Cron timekeeper for H1 scanner triggering.
- `services/media-forensics/` — optional web-side media-forensics service used by Fact Check when configured.
- `mobile/` — Expo SDK 57 / React Native native shell for Android and iOS. Uses the Vercel admin APIs as its source of truth and stores only the Dashboard API key in device SecureStore.
- `mt5/OAK_Cloud_Manager_EA.mq5` — standalone MQL5 execution/account-management runtime attached directly to each controlled MT5 terminal.
- `mt5/OAK_NeoTech_Compliance_EA.mq5` — optional, read-only C5 helper. v1.09 works standalone with a local C5 popup and chart `C5 LOOK`, auto-binds the active MT5 login/server across account switches, and can optionally forward the same reminder/`/look` through an already-provisioned OAK Local Telegram controller. The 14-rule assessment remains in the separate ReadOnly Connector/dashboard. `/neotech` publishes a one-click Windows Setup, direct EX5, checksums and guide.
- `local-failover/` — maintained PC-local Telegram failover plus ICMarkets H1 reader/publisher used for live snapshots, TP milestones and bounded retained-history backfill.
- `.github/workflows/` — web CI, mobile Android/iOS builds, plus H1/Telegram cloud fallback schedulers.

## Runtime flow

```text
Telegram / web schedule
        |
        v
Vercel control plane -> Upstash mailbox -> OAK_Cloud_Manager_EA -> MT5 broker

ICMarkets MT5 / cTrader H1 data -> Vercel H1 scanner -> Upstash public feed -> /engine + Telegram
                ^                    ^                              |
                |                    |                              v
        local-failover       Cloudflare H1 timekeeper       /api/mobile/h1 -> Android / iOS
```

There is no maintained desktop/Tauri runtime. MT5 trade execution is owned by the EA; cloud orchestration is owned by the web control plane, while `local-failover/` provides the maintained PC-local Telegram/H1 support path and does not replace the EA as trade executor.

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

## Mobile development

See `mobile/README.md`. The native shell uses pnpm and Expo prebuild; generated `android/` and `ios/` projects are intentionally ignored and recreated in GitHub Actions. The workflow publishes an Android debug APK and an unsigned `iphoneos` `.ipa` intended for third-party re-signing when mobile code changes.

## MT5 EA

See `mt5/README.md` for MT5 setup documentation. The independent NeoTech compliance source is `mt5/OAK_NeoTech_Compliance_EA.mq5` plus `mt5/neotech/`.

The NeoTech surface is unofficial/advisory and does not grant or claim NeoTech approval. Its backend validates transport/schema and renders stored MQL5 conclusions; it does not implement a second TypeScript compliance engine.

Never commit populated MT5 `.set` files, Upstash tokens, compliance ingest keys, broker credentials or Vercel secrets.
