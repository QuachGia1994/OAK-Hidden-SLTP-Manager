# ROBOT SLTP / OAK Gatekeeper Architecture

> updated 2026-08-22 · v4.1.0

This document describes the maintained production surfaces after retiring the Engine5/Pattern5 H4 stack.

## Product surfaces

- `dashboard/`: Next.js cloud control plane and web UI.
- `robot-sltp-pro/`: Tauri desktop fallback/diagnostic workstation.
- `domain/`, `services/`, root Python: local fallback runtime and MT5 utilities.
- `mt5/`: app-free OAK MQL5 EA runtime for MT5 execution/account management.

## Ownership map

| Concern | Canonical owner | Consumers |
| --- | --- | --- |
| H1 scanner v7 pattern/signal semantics | `dashboard/src/lib/h1-cloud-scanner.ts` | cloud scanner route, tests |
| Cloud H1 market-data transport | `dashboard/src/lib/ctrader-json.ts` | `/api/h1-scanner/run`, read-only account status |
| Cloud scanner orchestration/state/Telegram publication | `dashboard/src/app/api/h1-scanner/run/route.ts` | Cloudflare timekeeper + GitHub fallback |
| H1 primary timekeeper | `cloudflare/h1-timekeeper/src/index.js` | Cloudflare Durable Object Alarm + watchdog Cron |
| Public H1 transport contract | `dashboard/src/lib/h1-signals.ts` | `/engine` server page and H1 UI |
| H1 web rendering/detail | `dashboard/src/components/H1EngineBoard.tsx`, `H1SignalBoard.tsx` | browser |
| VIP H1 redaction | `dashboard/src/lib/vip.ts` | `/engine` server page |
| Telegram cloud command parsing | `dashboard/src/lib/telegram-cloud-domain.ts` | Telegram webhook |
| Telegram cloud intent/audit/idempotency store | `dashboard/src/lib/telegram-cloud-store.ts` | webhook, due tick, confirm-gated execution |
| Telegram cloud webhook | `dashboard/src/app/api/telegram/webhook/route.ts` | Telegram Bot API |
| Telegram due scheduler | `dashboard/src/app/api/telegram/tick/route.ts` | Cloudflare minute clock + GitHub OIDC fallback |
| cTrader OAuth/token vault | `dashboard/src/app/api/ctrader/*`, `dashboard/src/lib/ctrader-vault.ts` | scanner, account manager, Telegram status/positions |
| Provider account registry | `dashboard/src/lib/provider-accounts.ts`, `provider-account-domain.ts`, `/api/accounts`, `/accounts` | admin web UI, Telegram `/profiles`, provider execution routing |
| cTrader managed accounts + default protection | `dashboard/src/lib/ctrader-accounts.ts` | cTrader discovery/targeting, provider registry adapter |
| cTrader cloud Auto Manager | `dashboard/src/lib/ctrader-account-manager.ts`, `ctrader-manager-domain.ts` | minute tick, entry netting, SL/TP repair, BE/R/partial management |
| Multi-provider execution router | `dashboard/src/lib/telegram-cloud-execution.ts` | `/approve ID`, pre-approved scheduled intents |
| cTrader mutation/read adapter | `dashboard/src/lib/ctrader-json.ts` | provider execution router, cTrader Auto Manager |
| MT5 outbound mailbox bridge | `dashboard/src/lib/mt5-bridge.ts`, `mt5/OAK_Cloud_Manager_EA.mq5` (primary app-free runtime), `domain/mt5_cloud_bridge.py` + `domain/monitor_worker.py` (legacy fallback) | provider execution router, `/positions`, attached MT5 terminal |
| Local fallback H1 scanner | `domain/xau_h1_pattern_scanner.py` | `MonitorWorker` when explicitly run locally |
| Local fallback H1 public publisher | `domain/h1_signal_public_feed.py` | Upstash H1 feed |
| Desktop IPC/runtime | `robot-sltp-pro/backend_bridge.py`, `src/backend-client.ts` | Tauri UI |
| MT5 attach/start safety | `services/mt5_service.py`, `services/mt5_terminal_service.py` | local observation/fallback runtime |
| H1 parity | `robot-sltp-pro/h1_market_data.py` + H1 snapshot CLIs | migration/regression only |

## H1 scanner rule v2

The production scanner is cloud-primary and operates only on H1 data for the current broker day.

### Pattern sources

Pattern-source mapping:

- `AUDUSD` → pattern source for `XAUUSD`.
- `GBPUSD` → pattern source for `EURUSD`, `AUDUSD`, `USDCAD`, and `USDJPY`.

The output target set remains:

`XAUUSD, EURUSD, AUDUSD, USDCAD, USDJPY`.

### Pattern classes

Patterns are read newest → oldest at scanner slot `Hn`. Exactly three source classes exist:

- `TG` / `GT` → `sw2` / SW 2 cây, opening class at H03 only using H02→H01.
- `TGG` / `GTT` → `sw3Pure` / SW 3 cây thuần.
- `TTT` / `GGG` → `sw3Normal` / SW 3 cây thường.

`sw3Normal` is valid only for an exact three-candle run at the current slot. If the immediately older H1 candle has the same direction, the run is already four candles or longer (`TTTT…` / `GGGG…`) and that current slot is guarded/skipped. `TGT/GTG` and `TGTG/GTGT` are not scanner source patterns.

### Base H1 and signal transform

At slot `Hn`, all bases are the first closed backward candle `H(n-1)` from the same broker day.

- XAUUSD: pattern = AUDUSD; base = GBPUSD.
- EURUSD: pattern = GBPUSD; base = EURUSD.
- AUDUSD: pattern = GBPUSD; base = AUDUSD.
- USDCAD: pattern = GBPUSD; base = USDCAD.
- USDJPY: pattern = GBPUSD; base = USDJPY.

Base direction: `T → BUY`, `G → SELL`.

All three pattern classes keep the base signal unchanged. A separate broker-calendar post-signal layer may invert the result:

- Monday: H03, H04, H09-H11, H12-H14 invert.
- Tuesday: H03, H04, H09-H11 invert.
- Wednesday: H03, H04, H12-H14 invert.
- Thursday: normally no inversion. The monthly flag is recalculated at the Thursday immediately before the first Friday whose day-of-month is 1-7; that Thursday cycle inverts only when its previous Wednesday is day 30 or 1, and the flag carries weekly until the next recalculation.
- Friday: the monthly flag is recalculated on the first Friday whose day-of-month is 1-7; it inverts when that anchor Friday is day 3, 4, or 7, and the flag carries weekly until the next recalculation.

There is no target-side post-check. Every accepted `sw3Pure` alert is marked `/!\\` in Telegram and the web cell. If another `sw3Pure` appears exactly two slots after the previous accepted pure, that second slot is skipped completely and pure tracking resets from the next slot. Example: H04 + H06 pure => H06 is omitted and scanning starts fresh from H07; H06 + H08 pure => H08 is omitted and scanning starts fresh from H09.

No day classification, Pattern5 group, H4 block, previous-day fallback, or cross-timeframe fallback exists in this scanner.

### Time and replay behavior

- Eligible scan slots: H03 through H17.
- Cloudflare Worker `oak-h1-timekeeper` is the primary clock. One SQLite Durable Object keeps a single alarm armed for the next exact top-of-hour boundary, calls the private Vercel scanner route from `alarm()`, and arms the next boundary only after a successful scanner outcome.
- `already-running`, `awaiting-closed-h1`, `disabled`, non-2xx and malformed scanner responses are treated as failures by the Durable Object so Cloudflare alarm retry semantics stay active instead of silently advancing the clock.
- Cloudflare Cron watchdogs at minutes `10`, `30`, and `50` check the current boundary. If that boundary has no recorded successful scanner call, the watchdog catches it up immediately and then re-arms the next H:00 alarm.
- GitHub starts redundant pre-boundary runners at minutes `10`, `30`, and `50` only as tertiary fallback. Each runner that starts before the boundary waits until the next H:00 and calls the same private route; Redis locking makes concurrent calls idempotent.
- H1-related pushes to `main` also trigger the GitHub workflow. The push run waits until GitHub reports the Vercel deployment for that exact commit as `success`, then calls the scanner once to warm the public feed immediately.
- Vercel retries for roughly 17.5 seconds when the just-closed H1 candle is not yet visible from cTrader.
- Cloudflare uses a dedicated random timekeeper bearer. The Worker stores the plaintext only as a Cloudflare Secret; Vercel compares its SHA-256 against a value stored in Upstash.
- Redis NX/EX lock prevents overlapping Cloudflare, GitHub or manual scanner invocations.
- Cloud state schema is v8. Public transport remains schema v7 with `signalRuleVersion=2`; older rule payloads are not reinterpreted. Pre-cutover slots are suppressed through the current broker hour to prevent replay, and current-day web history is rebuilt from current H1 data without resending Telegram alerts.
- Telegram must acknowledge a new signal before the alert is persisted.
- Public Upstash H1 feed is schema v7; skipped paired-pure slots never enter state/feed/Telegram/web.
- There is no target-side post-check, STOP-H17 overlay, day classification, Pattern5 block, or H4 dependency.

The local Python fallback mirrors the same rule-v2 source/base, calendar post-signal, guard and paired-pure reset semantics.

## `/engine` web flow

`/engine` is H1-only:

1. Server reads the latest H1 schema-v7 feed from Upstash.
2. Future broker days are masked.
3. Weekday VIP redaction is applied server-side.
4. `H1EngineBoard` displays cloud profile metadata (`cTrader IcMarkets`).
5. `H1SignalBoard` shows delivered BUY/SELL cells and the scanner/base explanation published by the backend.

The retired Engine5/Pattern5 H4 feed is not fetched or rendered.

## Telegram cloud control

Cloud webhook is the primary receiver. The webhook validates:

- Telegram secret-token header;
- exact configured admin chat ID;
- Redis `update_id` idempotency.

Maintained management/read commands include `/status`, `/profiles`, `/positions`, `/pending`, `/del ID`, `/del all`, plus intent capture for entry/close/modify requests, provider-scoped dynamic `/partial` rules for cTrader Auto Manager or MT5 OAK EA, and the explicit broker boundary `/approve ID`.

`/accounts` is an admin-only multi-provider web account manager backed by a signed HttpOnly session. cTrader OAuth can be reconnected and live/demo accounts are discovered through Open API; those accounts retain per-account FX/gold SL/TP defaults and an explicit opt-in Auto Manager configuration (auto SL/TP repair, entry netting, BE at R, close at R, R partials, max lot/exposure). MT5 accounts are represented separately as bridge metadata containing broker, login, environment, label and optional local bridge-profile name. No MT5 broker password is accepted by this web route. OAuth access/refresh tokens, cTrader client secrets, vault material and broker passwords remain server/local-only and are never returned to browser JavaScript.

The unified provider registry assigns explicit IDs (`ctrader:<accountId>` or generated `mt5:<id>`), enable state and an optional default account. Telegram `/profiles` renders this unified registry. A command with no account alias targets all enabled provider accounts; an explicit alias must resolve to exactly one account or the command fails closed rather than fanning out ambiguously.

cTrader mutations stay server-side through Open API. When a cTrader account's Auto Manager is enabled, the existing authenticated minute tick opens a fresh trading session, reads reconcile state plus backend-computed unrealized P&L and first live spot quotes, then evaluates automatic SL/TP repair, break-even at R, full close at R, configured R partials, and cloud-armed partial close by floating profit or directional target price. Cloud entries use the same manager settings for same-direction suppression, opposite-position close, opposite-pending cancellation, and max lot/exposure guards before the new market order. Per-position initial risk/original volume and dynamic rules live in Redis; every broker mutation has a per-position ledger. A running/uncertain mutation is reconciled on the next fresh snapshot and is never blindly replayed if the desired result cannot be proven. Auto Manager defaults OFF for existing/newly discovered cTrader accounts, so deployment alone cannot start managing live positions.

MT5 uses an outbound-only Upstash mailbox with two mutually compatible runtimes. The primary app-free path is `mt5/OAK_Cloud_Manager_EA.mq5`: an EA attached directly to the broker terminal publishes a short-lived `mql5-ea` heartbeat bound to `bridgeProfile` + live login, claims the same Redis arbiter key, and executes entry/close/modify/positions without the desktop app or Python worker. It also manages manual/mobile positions with automatic SL/TP, entry netting, break-even at R, full close at configured R, R partials, and cloud-armed partial close by floating profit or price. The previous `MonitorWorker`/Python bridge remains a legacy fallback and publishes `runtime=python-worker`; MT5 dynamic `/partial` fails closed unless the heartbeat runtime is `mql5-ea`. The cloud never receives an MT5 broker password and no inbound port is required. A cloud timeout may cancel only an unclaimed task; once either runtime has claimed it, timeout becomes `uncertain` and the same task is never automatically replayed.

Every broker-mutating Telegram command still starts as `approval_required`. Provider account IDs and per-account SL/TP distances are snapshotted into the intent before approval. `/approve ID` is required exactly once: an immediate intent executes after that confirmation; a future intent becomes `scheduled` and may execute only after its due time. Unapproved due intents are only reminded, never sent to the broker. Redis update idempotency plus a per-intent execution lock prevent webhook/tick retries from duplicating the same intent execution. Legacy stored numeric cTrader target IDs are normalized to `ctrader:<id>` when read so pre-existing pending intents remain valid.

Cloudflare calls the Telegram due tick every minute with a dedicated hashed bearer, while the existing GitHub OIDC workflow remains fallback. The same tick evaluates enabled cTrader Auto Manager accounts even if Telegram control is disabled; scheduled broker intents still execute only after crossing the explicit `/approve` boundary. cTrader BE/R/price/profit rules therefore have minute-level evaluation granularity, while already-attached cTrader SL/TP remains broker-native between cloud ticks.

`oak_enginecore.py` is fallback-only. It calls Telegram `getWebhookInfo` before acquiring its local singleton lock and exits when the cloud webhook is active; it never deletes/steals the cloud webhook merely because desktop is opened.

## Desktop fallback

The desktop no longer contains Engine5/Pattern5 UI or commands. It remains useful for:

- observing configured MT5 profiles;
- legacy fallback servicing of the outbound cloud mailbox when an OAK MQL5 EA is not attached;
- inspecting account/position snapshots from an already-running terminal;
- local SLTP configuration and legacy local pending-task administration;
- explicit local runtime start/stop and diagnostics.

Profile selection is attach-only. Selecting/refreshing a profile must not auto-start MT5.

## H1 parity utilities

The retained cTrader/MT5 parity path is H1-only. `market_data_provider.py` now owns only the canonical `Candle` value type used by H1 utilities.

- cTrader snapshot: `ctrader_snapshot_cli.py` + `ctrader_h1_market_data.py`.
- MT5 baseline: `mt5_h1_snapshot_cli.py`.
- normalization/comparison: `h1_market_data.py` + `h1_market_data_parity_cli.py`.

Pass/fail is broker-day H1 slot presence plus T/G direction. OHLC difference is diagnostic only.

## Failure behavior

- Missing/malformed H1 feed → no actionable web signal.
- Missing scanner/base candle → no signal for that slot until required data is available.
- Telegram send failure → state is not advanced.
- Corrupt local state → fallback scanner fails closed.
- cTrader token/account mismatch → cloud read fails closed.
- cTrader Auto Manager disabled → no automatic management mutations; deployment alone is inert for that account.
- cTrader manager mutation returns an ambiguous outcome → ledger becomes `uncertain`; the next tick may reconcile a proven result but cannot blindly repeat the mutation.
- cTrader live quote/P&L unavailable for a cycle → R/profit/price-triggered actions are skipped fail-closed; SL/TP repair may still proceed from reconcile state.
- MT5 bridge offline or heartbeat login mismatch → task is rejected before enqueue/execution.
- MT5 dynamic `/partial` sent to anything except an `mql5-ea` heartbeat → rejected before enqueue.
- MT5 task claimed but final broker outcome not returned before timeout → cloud marks it uncertain and does not replay it automatically.
- Cloud webhook active → local Telegram receiver exits instead of racing it.

## Verification ownership

- Scanner semantics: `dashboard/src/lib/h1-cloud-scanner.test.ts`, `tests/test_xau_h1_pattern_scanner.py`.
- Public H1 contract: `dashboard/src/lib/h1-signals.test.ts`, `tests/test_h1_signal_public_feed.py`.
- Telegram cloud control: `dashboard/src/lib/telegram-cloud-domain.test.ts`, `telegram-cloud-route.test.ts`.
- MT5 EA/cloud mailbox contract: `dashboard/src/lib/mt5-bridge.test.ts`, `tests/test_oak_mt5_ea_contract.py`, `tests/test_mt5_cloud_bridge.py`.
- cTrader Auto Manager: `dashboard/src/lib/ctrader-manager-domain.test.ts`, `ctrader-execution.test.ts`, `provider-account-domain.test.ts`.
- cTrader H1/parity: `tests/test_h1_market_data.py` and snapshot/parity CLIs.
- Desktop bridge/runtime lifecycle: `robot-sltp-pro/test_backend_bridge.py`, runtime lifecycle tests.
