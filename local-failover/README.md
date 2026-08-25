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

The MT5 Account Manager itself (automatic SL/TP, BE, close-at-R, partial rules and netting) is already terminal-local and continues to run even when Upstash is unavailable. This failover adds a second path for Telegram commands and scheduled MT5 execution.

## Ownership and safety

- `InpLocalFailoverEnabled=true` enables the EA's PC-local mailbox and health/status file. It does not by itself take Telegram ownership.
- Controller state is persisted as V2: `STANDBY -> ARMING -> LOCAL_ACTIVE -> RECOVERING -> STANDBY`, with `BLOCKED_UNCERTAIN` for unsafe ownership or outcome ambiguity.
- Cloud remains primary while healthy. Activation requires both fresh/matching EA evidence of repeated cloud write failure and repeated independent PC-side Redis `SET ... EX` write-canary failures. `PING` is not used as write-capacity proof. Authentication/configuration failures such as 401/403 or malformed 4xx fail closed instead of activating local control.
- Handoff verifies the configured production webhook, calls Telegram `deleteWebhook` with `drop_pending_updates=false`, verifies the webhook is empty, and only then permits `getUpdates`. While local is active, any reappearing webhook blocks local execution.
- Local mutation intents use `L-<epoch>-<seq>` IDs and still require a separate `/approve L-...`; bare numeric cloud IDs are rejected. Multi-line messages remain atomic at the 10-line limit, and multiple MT5 accounts require explicit `@ACCOUNT` targeting.
- Cloud and local derive the same canonical mutation origin `tg:<updateId>:<commandIndex>:<normalizedProviderAccountId>`. Its hash identifies the FILE_COMMON ledger. `entry`, `close`, `modify`, and `partial` share the same durable per-origin claim/result fence before broker execution; `positions` is read-only and bypasses that mutation claim.
- If a retained final result exists for the same origin/digest, it is reconciled without broker re-execution. A claim without a final result becomes `UNCERTAIN`; automatic replay is disabled. This is a durable fail-closed fence, not a claim of absolute exactly-once broker execution.
- On cloud recovery, locally handled Telegram update IDs are fenced in the existing Redis idempotency namespace before `setWebhook`; the exact production webhook URL is verified after restore. Approved local schedules remain PC-owned through handback, while unapproved intents expire.

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

The same Telegram bot accepts the core MT5 grammar: `/status`, `/profiles`, `/positions [@ACCOUNT]`, `/pending`, `/buy`, `/sell`, `/close`, `/closeall`, `/modify`, `/partial`, `/approve`, and `/del`. Scheduled `HH:MM` / `HHhMM` entry/close syntax is retained. Mutation creation and approval remain separate steps, for example `/approve L-<epoch>-<seq>`.

## Verification and production boundary

The V2 behavioral source of truth is `behavior-cases.json` plus `failover-v2.behavior.test.mjs` (26 cases). Offline verification covers cloud/local origin parity, atomic origin-claim races, retained results, fail-closed uncertainty, Telegram ownership handoff/recovery and installer dry-runs.

The code is not installed or live merely because these checks pass. Production use still requires separate operator authorization for Scheduled Task installation, a controlled Telegram webhook handoff test, and a safe Upstash outage/quota simulation. No broker mutation should be introduced solely to test failover ownership.
