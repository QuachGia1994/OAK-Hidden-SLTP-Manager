# OAK Cloud Manager EA

`OAK_Cloud_Manager_EA.mq5` is the standalone MT5 execution/runtime for ROBOT SLTP. Attach one EA instance to one chart in each MT5 terminal/account that should be controlled. MT5 execution is owned by this EA; there is no maintained desktop/Python broker worker in the repository.

## Runtime flow

```text
Telegram / dashboard schedule
        |
        v
Vercel control plane -> Upstash mailbox -> OAK_Cloud_Manager_EA -> MT5 broker
```

The cloud remains the source of truth for Telegram intents, `/approve`, target accounts, and scheduled due times. For future entry/close intents, approve once; the cloud dispatches the task at the due time and the EA executes it. This avoids maintaining a second competing scheduler inside the terminal.

If the terminal/PC is offline at the due time, the bridge heartbeat expires and the mutation fails closed. The cloud does not blindly replay a task whose broker result is uncertain.

## Features

- Cloud `entry`, `close`, `modify`, `positions` using the existing provider-account registry and Upstash mailbox.
- Automatic SL/TP on cloud entries and on managed positions opened manually/mobile/web when protection is missing.
- Entry netting policy: skip same direction, close opposite positions, remove opposite pending orders before a new entry.
- Break-even at configurable R with optional point offset.
- Full close at configurable R (`InpCloseAtR`).
- R-level partial closes using `InpPartialRLevels` and `InpPartialPercents`.
- Telegram/cloud dynamic partial by floating profit or absolute price:
  - `/partial 123456 profit 200 0.02 @Vantage` arms ticket `123456` to close `0.02` lots once floating profit reaches account-currency `200`.
  - `/partial XAUUSD price 3456.70 0.01 @Vantage` arms the only matching XAUUSD position to close `0.01` lots when the directional target price is reached. If multiple positions match the symbol, use a ticket.
- Per-position management state persists in MT5 terminal Global Variables using `POSITION_IDENTIFIER`, so initial risk/R state survives EA reloads and netting ticket replacement.
- Account identity binding: if `InpExpectedLogin` does not match the live MT5 login, EA initialization fails.
- Cloud task arbitration uses the same Redis claim key as the web control plane so a cloud task has one durable execution owner.
- Upstash traffic is bounded: local position management stays tick-driven, while the cloud mailbox is checked every 10 seconds by default (runtime-clamped to 10–15 seconds). Heartbeat refresh and queue peek share one atomic Redis command, avoiding the previous 1-second idle polling load.
- Cloud market entry waits up to 2.5 seconds for the selected symbol to synchronize and expose a positive bid/ask tick before building the broker request. This handles Market Watch warm-up races without retrying any broker mutation.

## Install

1. Open the target broker's MT5 terminal and log in to the intended account.
2. Open MetaEditor (`F4`). Copy `OAK_Cloud_Manager_EA.mq5` into the terminal's `MQL5/Experts/OAK/` folder and compile it.
3. In MT5 go to **Tools -> Options -> Expert Advisors**. Enable algorithmic trading and add the exact `https://...upstash.io` REST base URL used by ROBOT SLTP to **Allow WebRequest for listed URL**.
4. Attach `OAK_Cloud_Manager_EA` to one chart. One EA instance is enough to manage the whole logged-in account; do not attach multiple copies with the same bridge profile.
5. Set:
   - `InpBridgeProfile` = the MT5 account's `bridgeProfile` shown/configured in `/accounts`.
   - `InpExpectedLogin` = exact MT5 login number.
   - `InpUpstashRestUrl` and `InpUpstashRestToken` = the same bridge Redis REST credentials as the cloud control plane.
   - `InpCloudPollSeconds` = keep `10` for the normal balance of command usage and cloud execution latency. The runtime clamps this value to 10–15 seconds; `InpPollSeconds` remains the local manager timer and does not control Redis queue frequency.
   - SL/TP, netting, BE/R and exposure guards as required.
6. Keep **Algo Trading** enabled. `/accounts` and `/status` should show the bridge online after the EA heartbeat appears.
7. Verify with `/positions @ACCOUNT` before approving any live broker mutation.

## Security

`InpUpstashRestToken` is a secret. Never commit it, paste it into screenshots, or save/share a populated `.set` file. The repo ignores MT5 `.set` and compiled `.ex5` files. A dedicated Upstash database/token for broker execution is preferable to reusing a database that contains unrelated application state.

The EA validates both `bridgeProfile` and the live MT5 login before executing a cloud task. Dynamic `/partial` commands are accepted by the cloud only when the heartbeat identifies the runtime as `mql5-ea`.

## Management semantics

`R` is based on the position's initial risk distance: existing SL distance when the EA first sees the position, otherwise the configured default SL points. That risk is persisted before BE moves, so moving SL to entry does not redefine R.

For one configured partial percentage, each R trigger closes that percentage of the then-current volume. For multiple percentages, each percentage is based on the original managed volume. Partial closes respect the broker's minimum volume/step and retain at least the broker minimum when the rule is explicitly partial.

`InpManageMagic=-1` manages positions regardless of origin, including manual/mobile orders. Set a specific magic or `InpManagedSymbols` if the EA must not touch all positions on the account.

## Operational boundary

The PC may be shut down on weekends if no MT5 cloud work is expected. While the terminal is closed, MT5 bridge status is offline and no EA-side BE/partial/protection logic can run. Broker-native SL/TP already attached to positions remains active at the broker even when the PC is off.

## NeoTech compliance EA — independent, read-only

`OAK_NeoTech_Compliance_EA.mq5` is a separate MQL5 EA for technical/advisory NeoTech compliance review and is isolated from all trading/execution/scanner/failover surfaces. MQL5 (`OAK_NeoTech_Compliance_EA.mq5` plus `neotech/`) is the only source of truth for compliance formulas and criterion conclusions; the dashboard only authenticates/validates report structure, stores immutable reports/audit and renders `/check` through the existing Telegram bot/webhook. This project does not claim official NeoTech approval.

The compliance surface is read-only with respect to the broker. It reads account/order/deal/position/price history, samples current balance/equity, persists bounded local evidence/checkpoints and may upload JSON by `WebRequest`. It contains no order send, trade class, close/modify/delete or other broker-mutation path. `OnTradeTransaction` records bounded prospective evidence/dirty state only; historical FDD reconstruction and network upload are timer-owned.

### Install and bind the account

1. Open the intended MT5 account and MetaEditor. Compile `OAK_NeoTech_Compliance_EA.mq5` together with `neotech/NeoTechComplianceCore.mqh` and `neotech/NeoTechComplianceJson.mqh`; require zero compiler errors and warnings.
2. Attach the compliance EA to one chart in the intended account. It does not need or use Algo Trading permission to mutate trades because no trade-mutation code exists.
3. Set `InpExpectedLogin` to the exact current MT5 login. Initialization fails if it is zero or does not match the attached account.
4. Set `InpProfileSlug` to the backend opaque profile slug (`[a-z0-9_-]`, 6–32 chars) and `InpIngestKey` to that profile's secret ingest key. Do not put the raw login in the slug.
5. Add `https://www.oakgatekeeper.uk` to **Tools -> Options -> Expert Advisors -> Allow WebRequest for listed URL** when uploads are enabled. `InpIngestUrl` defaults to `https://www.oakgatekeeper.uk/api/neotech/compliance/report`; HTTPS is mandatory.
6. For Gold C6 distance, set `InpGoldPipSizeOverride` when the broker's Gold pip convention has been independently verified. If the pip size cannot be established, a short Gold signal cannot become a confirmed no-SL/TP violation from missing distance evidence.
7. Optional manual pauses use `InpManualPausePeriods` as server-local `YYYY-MM-DD/YYYY-MM-DD;...`. A pause that intersects a deficient completed week changes that week to `NOT_VERIFIABLE`; it does not silently remove the week.

The EA derives a non-public account fingerprint as SHA-256 of `login|broker-company|server`. The report contains the fingerprint and a masked account ID, never the raw login. Backend configuration must register the same expected fingerprint, so a valid profile key cannot upload another MT5 account's report under that profile.

Example server profile configuration (placeholders only):

```json
[
  {
    "slug": "oakdemo",
    "accountFingerprint": "<64-hex-sha256>",
    "ingestKeySha256": "<64-hex-sha256-of-ingest-key>",
    "public": false,
    "ownerTelegramUserId": "<telegram-user-id>",
    "allowedChatIds": [],
    "allowedUserIds": []
  }
]
```

Set this JSON in `NEOTECH_COMPLIANCE_PROFILES_JSON`. `NEOTECH_COMPLIANCE_STALE_SECONDS` optionally changes Telegram stale-report labeling (minimum accepted value 300 seconds; default 36 hours). Keep the plaintext ingest key only in the MT5 input/runtime secret location; backend configuration stores its SHA-256, not the plaintext key.

### Report authentication and immutable storage

Each upload carries the profile slug, ingest key, UTC request timestamp, one-time nonce and `Idempotency-Key`. Schema v2 deliberately has no self-declared `reportHash` field. The EA computes SHA-256 over the exact UTF-8 JSON request body and sends that 64-hex digest as `Idempotency-Key`; the backend independently hashes the exact raw body and rejects a mismatch before immutable storage. The server-computed payload hash is the immutable report key. Replay nonces, wrong scoped keys, account-fingerprint mismatches, malformed/inconsistent nested reports and far-future `generatedAtUtc` values fail closed.

Backend schema validation checks report shape and internal consistency (criterion IDs, totals, occurrence/evidence counts, chronological ranges, bounded percentages and account/profile binding). It does not recompute C1–C9 formulas. Redis compliance audit is bounded; it does not grow without limit.

### `/check` through the existing Telegram bot

No second bot is created. The existing cloud webhook routes only the NeoTech `/check` command/callback to the stored compliance report:

- `/check @profile` — summary.
- `/check @profile violations` — confirmed HARD evidence plus RISK/unknown evidence.
- `/check @profile c1`, `c5`, `c6` — criterion detail.
- `/check @profile weeks` and `/check @profile months` — readable Vietnamese period detail.
- Append a page number when needed, for example `/check @profile c5 2`; callback buttons use the same deterministic pagination contract.

Private profiles require owner/user/chat ACL; public profiles may be viewed without that private ACL. Telegram output never exposes the raw MT5 login or ingest key. Detail pages include server-local time, UTC offset/normalized UTC, Vietnam time, symbol, position/order/deal tickets, measured value, threshold, reason, evidence source/confidence and HARD versus RISK. Oversized evidence is split losslessly below the Telegram message limit rather than truncated.

### PASS, FAIL and incomplete evidence

A confirmed violation can produce `FAIL` even when older history is incomplete. An absence-based `PASS` is allowed only when the evidence streams required by that criterion are complete. Otherwise the report uses `DATA_GAP`, `NOT_VERIFIABLE`, `IN_PROGRESS` or `RECONSTRUCTED` as appropriate. In `/check`, `UNKNOWN` is the umbrella label for `NOT_VERIFIABLE`, `DATA_GAP` and `RECONSTRUCTED`; `IN_PROGRESS` remains separate for an unfinished participation window. In particular, missing historical order/deal coverage cannot produce absence-based E1/E5/C5/C6/C4/C7/C9 PASS.

C6 has a prospective bounded SL/TP journal from the time this EA observes a position. A short closed signal may be a confirmed C6 FAIL only when the continuous observed timeline is complete and proves no SL/TP distance exceeded 30 pips. MT5 historical deals/orders do not prove every past SL/TP modification, so short trades predating complete journal coverage remain `NOT_VERIFIABLE`; a missing historical snapshot is never interpreted as "no SL/TP". Restarting with an active journal row also breaks completeness for that row until a new fully observed episode begins.

### FDD reconstruction and performance

Prospective extrema are exact only for the interval continuously observed while the EA is attached. Historical floating drawdown is reconstructed at account level, not per-position: the job processes chronological deal/cash-flow/quote events, carries the latest valid bid/ask per simultaneously active symbol, marks all open exposure with broker `OrderCalcProfit`, applies realized P/L/commission/swap/fee/balance events at their event times and records aggregate balance/equity, floating-loss percentage, peak-to-trough drawdown, worst timestamp and contributing position IDs/symbols.

Historical work is resumable/checkpointed in bounded `FILE_COMMON` state. Timer invocations process time slices under `InpReconstructionBudgetMs`; the job does not rescan the entire year every 15 seconds and tick requests have an explicit maximum count. Missing quote/conversion evidence creates `DATA_GAP`. When tick coverage is unavailable/too dense, M1 fallback uses conservative adverse low/high marks and remains explicitly `M1`/`RECONSTRUCTED`; historical reconstructed evidence is never promoted to an unconditional PASS.

### Time semantics

MT5/NeoTech server-local timestamps are carried separately from UTC. The report records server-local text, the configured NeoTech server UTC offset (UTC+2 November–March, UTC+3 April–October under this ruleset), normalized UTC where available, and Vietnam time (UTC+7). `generatedAtUtc` comes from `TimeGMT()`. Weeks, 30-day months, program start, history ranges and evidence retain their server-time basis instead of being mislabeled as UTC.

### Offline queue, cadence and removal

The timer defaults to 15 seconds. A changed/daily report is written to a bounded local pending file; failed/offline HTTPS uploads remain queued and retry on later timers. FDD and prospective extrema checkpoints are also local, so reconstruction resumes rather than restarting from the beginning. Telegram stale labeling makes old stored reports visible as stale instead of inventing fresh data.

To remove the compliance auditor, detach `OAK_NeoTech_Compliance_EA`, remove its compiled/source files from the terminal if desired, remove the NeoTech WebRequest allowlist entry when unused, delete the profile from `NEOTECH_COMPLIANCE_PROFILES_JSON`, and optionally delete that profile's `OAKNeoTechCompliance` files from MT5 `FILE_COMMON`. Removal does not require changing any trading/execution/scanner/failover component.

### Synthetic verification and troubleshooting

Compile `tests/NeoTechComplianceSyntheticTests.mq5` with the same `neotech/` includes, then execute it as an MT5 script in a demo/non-trading context. A successful run ends with the exact line `[NEOTECH SYNTHETIC] TOTAL=38 PASS=38 FAIL=0 RESULT=PASS`; failures print fixture name plus expected/actual. Compilation success alone is not a runtime PASS.

If initialization fails, first verify `InpExpectedLogin`, profile slug and account fingerprint registration. If upload stays queued, verify HTTPS, WebRequest allowlist, profile ingest key and server environment variables. `DATA_GAP` in FDD means required price/conversion evidence was missing; `NOT_VERIFIABLE` on historical C6 usually means the EA did not continuously observe that trade's SL/TP lifecycle. None of these statuses should be converted manually into PASS.
