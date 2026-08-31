# OAK PC Local Telegram Failover

This is the MT5 emergency path for a PC that stays online during the trading week. It does not replace the normal Vercel/Upstash control plane.

Normal mode:

```text
Telegram -> Vercel webhook -> Upstash intents/mailbox -> OAK MT5 EA
```

Verified failover mode:

```text
Telegram -> PC local controller -> MetaTrader FILE_COMMON mailbox -> OAK MT5 EA
```

Local-primary mode (config v3, `controlMode: "local-primary"`):

```text
Telegram -> PC local controller (getUpdates polling) -> FILE_COMMON mailbox -> OAK MT5 EA
Web dashboard: optional non-blocking H1 signal sync + visibility only
```

In local-primary mode the PC owns Telegram timing and MT5 execution. Vercel/Cloudflare/GitHub/Upstash are off the broker-mutation critical path: the controller deletes the Telegram webhook (taking ownership), polls `getUpdates` every second, and dispatches every mutation through the FILE_COMMON mailbox. The cloud is fenced fail-closed while local-primary runs (see below).

The MT5 Account Manager itself (automatic SL/TP, BE, close-at-R, partial rules and netting) is already terminal-local and continues to run even when Upstash is unavailable. This failover adds a second path for Telegram commands and scheduled MT5 execution.

## Local-primary mode

Config v3 is produced by `node .\local-failover\bootstrap-local-failover.mjs --local-primary`. It adds:

- `controlMode: "local-primary"` and `takeTelegramOwnership` (default `true`): on startup the controller observes the Telegram webhook; if one is active it is deleted (when consented) and the empty state is verified before any `getUpdates`. Without consent the controller stays `BLOCKED_UNCERTAIN`.
- Runtime EA identity: account selection matches EA heartbeats by `login`+`server` and takes `providerAccountId` from the live heartbeat. EA v1.05+ is mandatory — older EAs do not report a `providerAccountId` and local-primary refuses them (fail closed).
- Cloud fence heartbeat: while `LOCAL_ACTIVE` and Upstash credentials are configured, the controller writes `oak:telegram:local-primary:active:v1` (JSON `{at,epoch}`, `EX 300`, throttled to once per minute). Cloud routes treat the key's existence as "PC owns execution": `runCloudIntentExecution` throws, the webhook route refuses new intents and approve-execution, and the tick scheduler neither reinstalls the webhook nor executes due intents. Without Upstash credentials the fence degrades to off (Telegram webhook arbitration still prevents double ownership; the cloud self-heal can then reclaim after its 6h sync window).
- Optional web H1 signal sync: scheduled entry intents are queued in `pendingWebSync` and published to `webSignalUrl` (`POST /api/telegram/local-signal`, Bearer `DASHBOARD_API_KEY`) with a 5s timeout. Failures defer and retry; the path never blocks broker execution. Cancelled/expired intents drop their unpublished sync entries.
- Realtime scheduler: the controller loop wakes at the nearest scheduled `dueAt` (ms granularity, 50ms anti-busy-spin floor) instead of waiting a fixed tick, so a command like `buy XAUUSD 0.01 13h00 @fxce` dispatches within milliseconds of its due time — no minute cron (Cloudflare/GitHub/Vercel) and no Upstash polling participate in the timing path. Wall-clock remains authoritative for `dueAt`; duplicate execution is prevented by the durable `scheduled -> executing` status transition plus the FILE_COMMON origin fence, so clock drift cannot double-fire (a forward jump only pulls dispatch earlier within the 2-minute max-late window; a backward jump cannot re-dispatch a persisted intent). The EA polls the local mailbox on a millisecond timer (`InpLocalFailoverPollMs`, default 250ms) using monotonic `GetTickCount64()`. Timing evidence is persisted per intent: `scheduledAt`, `dispatchStartedAt`, `dueToDispatchMs`, `eaClaimedAt`, `eaFinishedAt`, `dispatchLatencyMs` (EA round-trip), and surfaced in the Telegram execution reply.
- Health: `--doctor` reports `controlMode`, `telegramOwnershipReady`, `controllerAlive`, `lastLoopAt`, `lockOwner` (single-instance pid/endpoint), fresh `localReady` EA statuses with EA versions, `pendingIntents`, `nearestDueAt`, `webSignalSyncConfigured`, `pendingWebSync`, `fenceHeartbeatConfigured`, `lastFenceHeartbeatAt`; Telegram `/status` mirrors the same surface (ownership, last loop, lock owner, EA versions, login/server match, pending intents, nearest due, web sync, fence heartbeat). No broker credential values are ever included.

### Cutover procedure (operator-authorized)

1. Compile and attach EA v1.05+ (`InpLocalPrimaryEnabled=true`) in every MT5 terminal; restart the terminals.
2. Cancel pending cloud intents from Telegram (`/del all`) so no stale armed cloud intent can execute if the fence ever lapses.
3. `node .\local-failover\bootstrap-local-failover.mjs --local-primary` (requires Upstash credentials for the one-time bootstrap ticket; `DASHBOARD_API_KEY` in `dashboard/.env.local` enables web signal sync).
4. Run the controller (`--doctor` first, then the Scheduled Task / foreground run) and verify: doctor reports `telegramOwnershipReady: true`, Telegram `/status` shows `local-primary · LOCAL_ACTIVE` with fresh EA heartbeats.
5. Deploy the web side (fence gates + `/api/telegram/local-signal`). This is independent of local execution and can follow later.

### Rollback

1. Stop the PC controller (fence key expires within 300s).
2. Restore the cloud webhook via the dashboard Telegram setup endpoint (`/api/telegram/setup`).
3. Put `controlMode` back to `failover` (or re-bootstrap without `--local-primary`) and restart the controller; it returns to `STANDBY` while the cloud webhook is verified active.

## Ownership and safety

- `InpLocalFailoverEnabled=true` enables the EA's PC-local mailbox and health/status file. It does not by itself take Telegram ownership.
- Controller state is persisted as V2: `STANDBY -> ARMING -> LOCAL_ACTIVE -> RECOVERING -> STANDBY`, with `BLOCKED_UNCERTAIN` for unsafe ownership or outcome ambiguity.
- Cloud remains primary while healthy. Activation requires both fresh/matching EA evidence of repeated cloud write failure and repeated independent PC-side Redis `SET ... EX` write-canary failures. `PING` is not used as write-capacity proof. Authentication/configuration failures such as 401/403 or malformed 4xx fail closed instead of activating local control.
- Handoff verifies the configured production webhook, calls Telegram `deleteWebhook` with `drop_pending_updates=false`, verifies the webhook is empty, and only then permits `getUpdates`. While local is active, any reappearing webhook blocks local execution.
- Local mutation intents use `L-<epoch>-<seq>` IDs. Timed entry/close intents auto-arm when saved; immediate mutations still require `/approve L-...`. A scheduled intent that misses its target by more than two minutes expires instead of executing late. Bare numeric cloud IDs are rejected. Multi-line messages remain atomic at the 10-line limit, and multiple MT5 accounts require explicit `@ACCOUNT` targeting.
- Cloud and local derive the same canonical mutation origin `tg:<updateId>:<commandIndex>:<normalizedProviderAccountId>`. Its hash identifies the FILE_COMMON ledger. `entry`, `close`, `modify`, and `partial` share the same durable per-origin claim/result fence before broker execution; `positions` is read-only and bypasses that mutation claim.
- If a retained final result exists for the same origin/digest, it is reconciled without broker re-execution. A claim without a final result becomes `UNCERTAIN`; automatic replay is disabled. This is a durable fail-closed fence, not a claim of absolute exactly-once broker execution.
- On cloud recovery, locally handled Telegram update IDs are fenced in the existing Redis idempotency namespace before `setWebhook`; the exact production webhook URL is verified after restore. Local scheduled intents remain PC-owned through handback, while immediate unapproved intents expire.

## Files and secrets

Runtime secrets/state are outside the Git repository under:

```text
%LOCALAPPDATA%\OAK Gatekeeper\
```

The MT5 local mailbox is under the MetaTrader shared Common Files directory:

```text
%APPDATA%\MetaQuotes\Terminal\Common\Files\OAKLocalFailover\
```

Never commit the generated `telegram-failover-config.json`. It contains the Telegram bot token, webhook secret and Upstash REST credential needed only for recovery fencing.

## Bootstrap and Scheduled Task lifecycle

Bootstrap copies the existing cloud Telegram/Upstash configuration and current online MT5 identity snapshot into the current Windows user's protected runtime directory. The bootstrap endpoint is POST-only, one-time-ticket fenced and no-store; secrets are not printed.

```powershell
node .\local-failover\bootstrap-local-failover.mjs
```

Before any install, run the read-only doctor. It validates Node 22+, the controller import graph, runtime config/ACL, FILE_COMMON path, current Windows SID and same-user running MT5 context:

```powershell
powershell -ExecutionPolicy Bypass -File .\local-failover\install-local-failover-task.ps1 -Action Doctor -DryRun
```

Preview lifecycle actions without mutating Task Scheduler:

```powershell
powershell -ExecutionPolicy Bypass -File .\local-failover\install-local-failover-task.ps1 -Action Install -DryRun
powershell -ExecutionPolicy Bypass -File .\local-failover\install-local-failover-task.ps1 -Action Status
powershell -ExecutionPolicy Bypass -File .\local-failover\install-local-failover-task.ps1 -Action Uninstall -DryRun
```

A real `-Action Install` is a separate operator-authorized step. Its task definition runs as the current interactive Windows user, quotes the controller path, uses `MultipleInstances IgnoreNew`, and has bounded restart-on-failure settings. Restart/reload each MT5 terminal after compiling EA v1.03 so `InpLocalFailoverEnabled=true` is active. Healthy operation remains `STANDBY`.

## Local command surface during failover

The same Telegram bot accepts the core MT5 grammar: `/status`, `/profiles`, `/positions [@ACCOUNT]`, `/pending`, `/buy`, `/sell`, `/close`, `/closeall`, `/modify`, `/partial`, `/approve`, and `/del`. BUY/SELL accepts both `SYMBOL LOT TIME [SL] [TP] [@ACCOUNT]` and legacy `SYMBOL LOT [SL] [TP] TIME [@ACCOUNT]`; bare `FXCE`/`Vantage` account aliases remain accepted without `@`. Scheduled `HH:MM` / `HHhMM` entry/close syntax auto-arms on creation and executes at the due time without `/approve`; a delay beyond two minutes expires the intent instead of placing a stale trade. Telegram displays a short numeric local intent ID, so operators use `/del 1` or `/approve 1`; the canonical `L-<epoch>-<seq>` ID remains internal for durable ledger/idempotency and is still accepted for diagnostics.

## Verification and production boundary

The V2 behavioral source of truth is `behavior-cases.json` plus `failover-v2.behavior.test.mjs` (38 cases; 27–32 cover local-primary ownership, runtime identity, web sync, the cloud fence heartbeat and overdue expiry; 33–38 cover exact-dueAt realtime dispatch, controller restart before dueAt, Telegram outage/reconnect, web-sync outage non-blocking, deterministic multi-account @ACCOUNT routing and fence heartbeat renewal/expiry). Offline verification covers cloud/local origin parity, atomic origin-claim races, retained results, fail-closed uncertainty, Telegram ownership handoff/recovery and installer dry-runs. Cloud-side fence gating is contract-checked in `dashboard/src/lib/telegram-cloud-route.test.ts`.

The code is not installed or live merely because these checks pass. Production use still requires separate operator authorization for Scheduled Task installation, a controlled Telegram webhook handoff test, and a safe Upstash outage/quota simulation. No broker mutation should be introduced solely to test failover ownership.
