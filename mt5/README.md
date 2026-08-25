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

`OAK_NeoTech_Compliance_EA.mq5` is a standalone MQL5 auditor. It reads the attached account's MT5 history, evaluates the NeoTech criteria and answers Telegram directly through the Bot API; no dashboard, Redis, webhook service or Vercel deployment is required. MQL5 (`OAK_NeoTech_Compliance_EA.mq5` plus `neotech/`) remains the only source of truth for formulas and conclusions. This project does not claim official NeoTech approval.

The compliance surface is broker-read-only. It reads account/order/deal/position/price history, samples balance/equity and stores bounded evidence/checkpoints in MT5 `FILE_COMMON`. It has no order-send, trade-class, close, modify or delete path. `OnTradeTransaction` only records prospective evidence and marks the cached report dirty.

### Install and bind the account

1. Compile `OAK_NeoTech_Compliance_EA.mq5` in MetaEditor together with the two `neotech/*.mqh` includes; require zero errors and zero warnings.
2. In MT5, add exactly `https://api.telegram.org` to **Tools -> Options -> Expert Advisors -> Allow WebRequest for listed URL**.
3. Attach one compliance EA instance to one chart on the intended account. Set `InpExpectedLogin` to that account's exact MT5 login; initialization fails closed on zero or mismatch.
4. Set `InpProfileSlug` to an opaque 6–32 character slug matching `[a-z0-9_-]`, for example `oakdemo`. Do not use the raw login as the slug.
5. Set `InpTelegramBotToken`, `InpTelegramAllowedChatIds` and `InpTelegramAllowedUserIds`. Both ACL lists are required and each incoming command must match both its chat ID and sender user ID. Values accept comma, space or semicolon separators.
6. Keep `InpTelegramDeleteWebhookOnInit=false` unless this bot is deliberately being moved from webhook delivery to this EA's `getUpdates` polling. If Telegram reports an active webhook, the EA blocks polling and never deletes it without this explicit opt-in.
7. `InpTelegramPollSeconds` controls the timer (1–300 seconds), `InpTelegramPageSize` controls rows per page (1–20), and `InpTelegramSendOnChange` optionally sends a changed summary to every allowed chat.
8. For XAUUSD C6 distance, set `InpGoldPipSizeOverride` only after verifying the broker's XAUUSD pip convention. Optional manual pauses use server-local `YYYY-MM-DD/YYYY-MM-DD;...` in `InpManualPausePeriods`.

The bot token is a runtime secret. Never commit it, log it, include it in screenshots or share a populated `.set` file. The account fingerprint is SHA-256 over `login|broker-company|server`; Telegram/report output uses the fingerprint and masked account identity, not the raw login, broker, server or token.

### Direct Telegram commands

- `/check @profile` — summary page 1.
- `/check @profile 2` — summary page 2.
- `/check @profile C5` — one criterion; valid tokens are E1–E3, E5, C1–C2 and C4–C9.
- `/check @profile violations 2` — violations page 2.
- In groups, Telegram's addressed form is accepted, for example `/check@NeoTechAuditBot @profile C5`.

Reply buttons use the same deterministic callback paging contract. Telegram output is concise Vietnamese and includes criterion totals plus, where evidence exists, the date/time, symbol, ticket identifiers, measured value, threshold and reason. Oversized detail is split below the message budget rather than silently truncated.

The displayed rules omit E4 and C3. E5 accepts only Forex symbols and XAUUSD. C2 requires every completed 30-day month to return at least 1%, with no annual averaging. C5 allows only one open order per symbol. C6 flags a close under 15 minutes unless an observed SL or TP exceeded 30 pips. C7 forbids simultaneous BUY/SELL on one symbol. C8 forbids copied signals but remains unverified without an authoritative external source. C9 flags balance deposits or withdrawals.

### PASS, FAIL and incomplete evidence

A confirmed violation can produce `FAIL` even when older history is incomplete. An absence-based `PASS` is allowed only when the evidence streams required by that criterion are complete. Otherwise the report uses `DATA_GAP`, `NOT_VERIFIABLE`, `IN_PROGRESS` or `RECONSTRUCTED` as appropriate. In `/check`, `UNKNOWN` is the umbrella label for `NOT_VERIFIABLE`, `DATA_GAP` and `RECONSTRUCTED`; `IN_PROGRESS` remains separate for an unfinished participation window. In particular, missing historical order/deal coverage cannot produce absence-based E1/E5/C5/C6/C4/C7/C9 PASS.

C6 has a prospective bounded SL/TP journal from the time this EA observes a position. A short closed signal may be a confirmed C6 FAIL only when the continuous observed timeline is complete and proves no SL/TP distance exceeded 30 pips. MT5 historical deals/orders do not prove every past SL/TP modification, so short trades predating complete journal coverage remain `NOT_VERIFIABLE`; a missing historical snapshot is never interpreted as "no SL/TP". Restarting with an active journal row also breaks completeness for that row until a new fully observed episode begins.

### FDD reconstruction and performance

Prospective extrema are exact only for the interval continuously observed while the EA is attached. Historical floating drawdown is reconstructed at account level, not per-position: the job processes chronological deal/cash-flow/quote events, carries the latest valid bid/ask per simultaneously active symbol, marks all open exposure with broker `OrderCalcProfit`, applies realized P/L/commission/swap/fee/balance events at their event times and records aggregate balance/equity, floating-loss percentage, peak-to-trough drawdown, worst timestamp and contributing position IDs/symbols.

Historical work is resumable/checkpointed in bounded `FILE_COMMON` state. Timer invocations process time slices under `InpReconstructionBudgetMs`; the job does not rescan the entire year every 15 seconds and tick requests have an explicit maximum count. Missing quote/conversion evidence creates `DATA_GAP`. When tick coverage is unavailable/too dense, M1 fallback uses conservative adverse low/high marks and remains explicitly `M1`/`RECONSTRUCTED`; historical reconstructed evidence is never promoted to an unconditional PASS.

### Time semantics

MT5/NeoTech server-local timestamps are carried separately from UTC. The report records server-local text, the configured NeoTech server UTC offset (UTC+2 November–March, UTC+3 April–October under this ruleset), normalized UTC where available, and Vietnam time (UTC+7). `generatedAtUtc` comes from `TimeGMT()`. Weeks, 30-day months, program start, history ranges and evidence retain their server-time basis instead of being mislabeled as UTC.

### Local state, polling and removal

The timer defaults to 15 seconds. Report cache, Telegram update offset, last-notified hash, FDD reconstruction and prospective SL/TP/extrema checkpoints use a `FILE_COMMON` namespace derived from the profile slug plus account fingerprint. A restart resumes the saved polling offset and reconstruction instead of replaying acknowledged updates or rescanning the whole horizon.

Telegram `getUpdates` uses `timeout=0`; failures use bounded exponential backoff. A cached report remains available while history refresh/reconstruction continues, but Telegram cannot answer while MT5 or this EA is stopped. Only one consumer should own a bot's updates.

To remove the auditor, detach `OAK_NeoTech_Compliance_EA`, remove its source/compiled files if desired, remove the `https://api.telegram.org` allowlist entry when unused, and optionally delete that profile/account namespace under `OAKNeoTechCompliance` from MT5 `FILE_COMMON`. No trading, dashboard or Vercel component needs changing.

### Synthetic verification and troubleshooting

Compile `tests/NeoTechComplianceSyntheticTests.mq5` with the same `neotech/` includes, then execute it as an MT5 script in an isolated demo/non-trading terminal. It never calls the real Telegram API. A successful run ends with the exact line `[NEOTECH SYNTHETIC] TOTAL=52 PASS=52 FAIL=0 RESULT=PASS`; failures print fixture name plus expected/actual. Compilation alone is not a runtime PASS.

If initialization fails, verify the login binding, slug, token, both ACL lists and input ranges. If polling is blocked, inspect `getWebhookInfo`: either keep the existing webhook owner or deliberately opt in once to `deleteWebhook`. For HTTP failures, verify the Telegram WebRequest allowlist and network access. `DATA_GAP` in FDD means required price/conversion evidence is missing; `NOT_VERIFIABLE` on historical C6 usually means the EA did not continuously observe that trade's SL/TP lifecycle. Never convert either status manually into PASS.
