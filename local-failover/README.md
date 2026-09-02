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
Scheduled ENTRY: Telegram -> PC scheduler -> EA entry_prepare guards -> MT5 order window messages -> EA position verification
Immediate ENTRY + close/modify/partial/positions: Telegram -> PC controller -> FILE_COMMON mailbox -> OAK MT5 EA
Web dashboard: optional non-blocking H1 signal sync + visibility only
```

In local-primary mode the PC owns Telegram timing and MT5 execution. Vercel/Cloudflare/GitHub/Upstash are off the broker-mutation critical path: the controller deletes the Telegram webhook (taking ownership), polls `getUpdates` every second, dispatches non-scheduled-entry actions through the FILE_COMMON mailbox, and sends only due scheduled entries through the MT5 UI adapter after retained EA preparation guards. The cloud is fenced fail-closed while local-primary runs (see below).

The MT5 Account Manager itself (automatic SL/TP, BE, close-at-R, partial rules and netting) is already terminal-local and continues to run even when Upstash is unavailable. This failover adds a second path for Telegram commands and scheduled MT5 execution.

## Local-primary mode

Config v3 is produced by `node .\local-failover\bootstrap-local-failover.mjs --local-primary`. It adds:

- `controlMode: "local-primary"` and `takeTelegramOwnership` (default `true`): on startup the controller observes the Telegram webhook; if one is active it is deleted (when consented) and the empty state is verified before any `getUpdates`. Without consent the controller stays `BLOCKED_UNCERTAIN`.
- Runtime EA identity: EA v1.10 heartbeats include a stable terminal-scoped `terminalId`. With `InpLocalProviderAccountId` blank, the EA derives `providerAccountId` from the currently logged-in `login`+`server`, detects account switches while it remains attached, and republishes the new identity. The controller reconciles that fresh heartbeat into the protected local-primary snapshot, preserves configured aliases such as `FXCE`, removes a stale duplicate alias instead of leaving ambiguous routing, and reapplies the user-only Windows ACL after the atomic config rewrite. EA v1.08+ remains mandatory for the scheduled UI-entry path because it adds guarded `entry_prepare` output and position comments used for post-submit verification; older EAs are refused (fail closed).
- Cloud fence heartbeat: while `LOCAL_ACTIVE` and Upstash credentials are configured, the controller writes `oak:telegram:local-primary:active:v1` (JSON `{at,epoch}`, `EX 300`, throttled to once per minute). Cloud routes treat the key's existence as "PC owns execution": `runCloudIntentExecution` throws, the webhook route refuses new intents and approve-execution, and the tick scheduler neither reinstalls the webhook nor executes due intents. Without Upstash credentials the fence degrades to off (Telegram webhook arbitration still prevents double ownership; the cloud self-heal can then reclaim after its 6h sync window).
- Optional web H1 signal sync: scheduled entry intents are queued in `pendingWebSync` and published to `webSignalUrl` (`POST /api/telegram/local-signal`, Bearer `DASHBOARD_API_KEY`) with a 5s timeout. Failures defer and retry; the path never blocks broker execution. Cancelled/expired intents drop their unpublished sync entries.
- Realtime scheduler: the controller loop wakes at the nearest scheduled `dueAt` (ms granularity, 50ms anti-busy-spin floor) instead of waiting a fixed tick, so a command like `buy XAUUSD 0.01 13h00 @fxce` dispatches within milliseconds of its due time — no minute cron (Cloudflare/GitHub/Vercel) and no Upstash polling participate in the timing path. With `scheduledEntryExecution: "mt5-ui"`, only a due `entry` uses the UI adapter; immediate entry and every close/modify/partial/positions action stay on the retained EA mailbox path. Wall-clock remains authoritative for `dueAt`; duplicate execution is prevented by the durable `scheduled -> executing` transition plus per-origin claim/result fences. The adapter first asks EA v1.08 for `entry_prepare` (same-direction guard, opposite netting, exposure/lot/tick validation and absolute SL/TP), converts machine-precision lots to MT5 manual-entry text, then fills, commits and clicks the exact MT5 order controls. Correct-lot snapshot verification releases the next queued entry immediately. It never calls global mouse/keyboard APIs. Timing evidence is persisted per intent and surfaced in the Telegram execution reply.
- Health: `--doctor` reports `controlMode`, `scheduledEntryExecution`, `telegramOwnershipReady`, `controllerAlive`, `lastLoopAt`, `lockOwner` (single-instance pid/endpoint), fresh `localReady` EA statuses with EA versions, `pendingIntents`, `nearestDueAt`, `webSignalSyncConfigured`, `pendingWebSync`, `fenceHeartbeatConfigured`, `lastFenceHeartbeatAt`; Telegram `/status` mirrors the operational surface. No broker credential values are ever included.

### Cutover procedure (operator-authorized)

1. Compile and attach EA v1.10 (`InpLocalPrimaryEnabled=true`) in every MT5 terminal; keep `InpLocalProviderAccountId` blank for automatic account rebinding, then restart the terminals. The controller and each terminal must run at the same Windows integrity level; an elevated terminal cannot be controlled by a limited controller.
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
- Local mutation intents use `L-<epoch>-<seq>` IDs. Timed entry/close intents auto-arm when saved; immediate mutations still require `/approve L-...`. A scheduled intent that misses its target by more than two minutes expires instead of executing late. Bare numeric cloud IDs are rejected. Multi-line messages remain atomic at the 10-line limit. Entry/modify/partial commands still require explicit `@ACCOUNT` when multiple MT5 accounts are enabled; close commands without `@ACCOUNT` intentionally fan out to all enabled MT5 accounts, while an explicit target stays single-account. `Đóng all lúc HHhMM` and `Đóng SYMBOL lúc HHhMM` are accepted aliases.
- Before a timed MT5 UI entry is reported as saved/armed, the controller asks the target EA to resolve the broker symbol, select it into Market Watch if needed, and verify that `SYMBOL_TRADE_MODE` permits the requested BUY/SELL side. A failed resolve/select/trade-mode check returns a Telegram warning and does not allocate or arm an intent.
- Trade-event reporting stays off the broker-mutation critical path. EA v1.09+ writes local FILE_COMMON event evidence for the first SL reach at/through break-even per position, broker `DEAL_REASON_SL` exits, filled pending orders and broker-confirmed partial-close deals that leave position volume open. The controller validates the event against the configured MT5 account + fresh EA identity, sends Telegram, retains failed deliveries for retry, and remembers account-scoped delivered event IDs across restarts to suppress callback/file replays without suppressing the same broker deal number on another account. Successful timed entry/order and timed close intents are separately queued for Telegram only after their broker/UI execution result is `executed` + `ok`; a Telegram outage never causes the broker mutation to run again.
- Cloud and local derive the same canonical mutation origin `tg:<updateId>:<commandIndex>:<normalizedProviderAccountId>`. Its hash identifies the FILE_COMMON ledger. `entry`, `close`, `modify`, and `partial` share the same durable per-origin claim/result fence before broker execution; the internal `entry_prepare` uses a separate canonical command-index namespace. `positions` and pre-confirmation `symbol_prepare` use read-style ledgers and bypass the broker-mutation claim; `symbol_prepare` may only change local Market Watch selection.
- If a retained final result exists for the same origin/digest, it is reconciled without broker re-execution. A claim without a final result becomes `UNCERTAIN`; automatic replay is disabled. After a UI submit, success is accepted only when the EA positions snapshot contains the exact `OAK:<ledger-prefix>` comment plus the expected symbol, side and lot; missing proof is `UNCERTAIN`, never an automatic retry. This is a durable fail-closed fence, not a claim of absolute exactly-once broker execution.
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

A real `-Action Install` is a separate operator-authorized step. Its task definition runs as the current interactive Windows user, quotes the controller path, uses `MultipleInstances IgnoreNew`, keeps the logon trigger, and adds a one-minute repeating self-heal trigger so an externally terminated controller is relaunched without waiting for the next logon. Restart-on-failure is retained, and battery transitions do not stop or block the controller. To intentionally keep local control stopped, disable or uninstall the task rather than only stopping its current process. Restart/reload each MT5 terminal after compiling EA v1.08 so `InpLocalFailoverEnabled=true` is active. Healthy operation remains `STANDBY`.

## Local ICMarkets H1 scanner

H1 rule v59 is independent of the trading EA and reads market data only from the logged-in ICMarkets MT5 terminal. `mt5-h1-market-reader.py` uses the MetaTrader5 Python API with `copy_rates_from_pos(..., TIMEFRAME_M15, ...)`; it never calls `order_send` or any position mutation API. On this MT5 API path the rate epoch fields expose terminal/server-wall components, so the reader decodes them directly and deliberately does not reapply the cTrader UTC→ICMarkets `UTC+2/UTC+3` conversion before evaluating `H3/H6/H9/H12/H14/H16`.

The publisher posts only T/G M15 evidence to the authenticated `/api/h1-scanner/local-market` route. Legacy cloud scanner/backfill endpoints remain authenticated but are no-ops, so cTrader cannot overwrite rule-v59 state. History uses the same local source and can be seeded for up to 90 calendar days.

```powershell
node .\local-failover\oak-local-h1-scanner.mjs --dry-run
node .\local-failover\oak-local-h1-scanner.mjs --backfill 90
powershell -ExecutionPolicy Bypass -File .\local-failover\install-local-h1-scanner-task.ps1 -Action Doctor
powershell -ExecutionPolicy Bypass -File .\local-failover\install-local-h1-scanner-task.ps1 -Action Install -DryRun
powershell -ExecutionPolicy Bypass -File .\local-failover\install-local-h1-scanner-task.ps1 -Action Status
```

The real H1 task runs once per minute as the interactive Windows user, starts at logon, uses `MultipleInstances IgnoreNew`, and does not stop on battery transitions. It is analytics-only: a task failure can make H1 Live stale but cannot place, close, or modify a broker order.

## Local command surface during failover

The same Telegram bot accepts the core MT5 grammar: `/status`, `/profiles`, `/positions [@ACCOUNT]`, `/pending`, `/buy`, `/sell`, `/close`, `/closeall`, `/modify`, `/partial`, `/approve`, and `/del`. BUY/SELL accepts both `SYMBOL LOT TIME [SL] [TP] [@ACCOUNT]` and legacy `SYMBOL LOT [SL] [TP] TIME [@ACCOUNT]`; bare `FXCE`/`Vantage` account aliases remain accepted without `@`. A `/close` or `/closeall` command without `@ACCOUNT` fans out to every enabled MT5 account after all target identities are validated; an explicit account remains single-target. Base FX/metal symbols match broker prefix/suffix variants inside each terminal. Scheduled `HH:MM` / `HHhMM` entry/close syntax auto-arms on creation and executes at the due time without `/approve`; a delay beyond two minutes expires the intent instead of placing a stale trade. Telegram displays a short numeric local intent ID, so operators use `/del 1` or `/approve 1`; the canonical `L-<epoch>-<seq>` ID remains internal for durable ledger/idempotency and is still accepted for diagnostics.

## Verification and production boundary

The V2 behavioral source of truth is `behavior-cases.json` plus `failover-v2.behavior.test.mjs` (39 numbered cases plus scheduled-entry routing and trade-event notification coverage; 27–32 cover local-primary ownership, runtime identity, web sync, the cloud fence heartbeat and overdue expiry; 33–39 cover exact-dueAt realtime dispatch, controller restart before dueAt, Telegram outage/reconnect, web-sync outage non-blocking, deterministic multi-account routing, fence heartbeat renewal/expiry and untargeted close fan-out). `mt5-ui-entry-adapter.test.mjs` adds focused coverage for preparation, no-replay claims, post-submit uncertainty, routing isolation and the no-global-input contract. Offline verification covers cloud/local origin parity, atomic origin-claim races, retained results, fail-closed uncertainty, Telegram ownership handoff/recovery and installer dry-runs. Cloud-side fence gating is contract-checked in `dashboard/src/lib/telegram-cloud-route.test.ts`.

The code is not installed or live merely because these checks pass. Production use still requires separate operator authorization for Scheduled Task installation, a controlled Telegram webhook handoff test, and a safe Upstash outage/quota simulation. No broker mutation should be introduced solely to test failover ownership.
