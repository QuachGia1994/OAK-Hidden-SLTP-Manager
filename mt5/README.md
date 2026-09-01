# OAK Local Manager EA

`OAK_Cloud_Manager_EA.mq5` is the local-only MT5 execution/runtime for ROBOT SLTP. Attach one EA instance to one chart per MT5 terminal. From v1.06, broker-control execution is exclusively `PC controller -> FILE_COMMON -> EA -> MT5`; the EA exposes no Upstash/cloud bridge credentials in Inputs and does not poll a cloud mailbox.

## Runtime flow

```text
Scheduled ENTRY save -> controller -> EA symbol_prepare -> Telegram saved/armed reply
Scheduled ENTRY due  -> controller -> EA entry_prepare -> targeted MT5 order-window messages -> broker
Other actions        -> controller -> MetaTrader FILE_COMMON -> OAK EA -> broker
Website signal  -> optional non-blocking H1 sync
```

The local controller owns Telegram timing and durable intent state. The website sync is visibility-only and cannot block broker dispatch. If the PC/terminal is offline at the scheduled time, the local stale-window rule fails closed rather than blindly replaying an old broker mutation.

## Features

- Local `entry`, `close`, `closeall`, `modify`, `partial`, and `positions` through FILE_COMMON; EA v1.08 introduced internal `entry_prepare` for scheduled UI entry. The current source also exposes non-broker `symbol_prepare` so the controller can resolve/select a broker symbol in Market Watch and reject disabled, close-only, or wrong-direction `SYMBOL_TRADE_MODE` before Telegram saves/arms a timed UI intent. EA v1.09 closes every matching broker prefix/suffix variant for a base FX/metal root, including the XAUUSD/GOLD alias.
- Automatic SL/TP on managed positions opened by EA, manual, mobile, or other permitted sources when protection is missing.
- Entry netting policy: skip same direction, close opposite positions, remove opposite pending orders before a new entry.
- Break-even at configurable R with optional point offset.
- Full close at configurable R (`InpCloseAtR`).
- R-level partial closes using `InpPartialRLevels` and `InpPartialPercents`.
- Dynamic partial by floating profit or absolute price.
- Per-position management state persists in MT5 terminal Global Variables using `POSITION_IDENTIFIER`.
- Runtime identity is derived locally from terminal login/server. Blank `InpLocalProfile` becomes `local_<login>`; blank `InpLocalProviderAccountId` becomes deterministic `mt5:<sha256-32>`.
- Broker mutations pass through a durable FILE_COMMON per-origin claim/result ledger. A retained result is reconciled without re-execution; a retained claim without a result is `UNCERTAIN` and is never replayed automatically.
- Market entry waits up to 2.5 seconds for symbol synchronization and a usable bid/ask before building the broker request. There is no blind broker retry after an ambiguous transport result.
- EA v1.06 removed all cloud bridge settings from MT5 Properties and stopped cloud polling from `OnTimer`.
- EA v1.07 lowers the local FILE_COMMON poll default to `100ms` and makes all partial closes round DOWN to broker volume step while always retaining at least one broker minimum-volume remainder.
- EA v1.08 adds internal `entry_prepare`: it preserves the existing same-direction skip, opposite-position/pending cleanup, exposure/lot/symbol/tick guards and absolute SL/TP calculation, then returns exact fields for the controller. Only a due scheduled entry may use those fields to click the exact MT5 Buy/Sell control via targeted window messages; immediate entries and all management actions remain EA-executed. No global mouse or keyboard injection is used.
- `symbol_prepare` runs before a timed MT5 UI intent is persisted. It uses broker-wide symbol discovery plus `SymbolSelect(..., true)` to add a missing symbol to Market Watch, returns the resolved prefix/suffix symbol for the Telegram confirmation, and checks the requested side against `SYMBOL_TRADE_MODE`. It does not send/close/modify an order. The same trade-mode check runs again at due-time `entry_prepare`/`entry` execution.

## Install

1. Open the target broker's MT5 terminal and log in to the intended account.
2. Copy/compile `OAK_Cloud_Manager_EA.mq5` into that terminal's `MQL5/Experts/` folder.
3. Enable **Algo Trading**. No Upstash URL and no cloud WebRequest allow-list entry is required for this EA.
4. Attach one EA instance to one chart.
5. Local PC Control:
   - `InpLocalProfile`: leave blank for `local_<login>` unless a stable local label is explicitly required.
   - `InpLocalProviderAccountId`: leave blank for deterministic terminal-derived identity.
   - `InpLocalPollMsV107`: default `100`; clamped to `100..5000` ms. The v1.07 variable name intentionally changed so already-attached charts do not preserve the old 250ms value.
6. Configure SL/TP, netting, BE/R and exposure guards as required.
7. Keep the PC local controller running 24/5. Use `/status`, `/profiles`, and `/positions @ACCOUNT` for read-only verification before any broker mutation.
8. For `scheduledEntryExecution: "mt5-ui"`, run the controller and each MT5 terminal at the same Windows integrity level. Prefer opening MT5 normally rather than **Run as administrator**; Windows blocks targeted messages from a lower-integrity controller to an elevated terminal.

## Security

EA v1.09 contains no Upstash/cloud token Input and no cloud broker-execution polling path. Local runtime secrets such as the Telegram bot token and dashboard sync API key stay outside Git under the Windows user-only local runtime directory. Do not share populated local configuration or screenshots containing secrets.

Local-only execution improves privacy by keeping broker mutations inside the user's MT5 terminal, but it is not a claim that an EA or its orders are undetectable to a broker.

## Management semantics

`R` is based on the position's initial risk distance: existing SL distance when the EA first sees the position, otherwise the configured default SL points. That risk is persisted before BE moves, so moving SL to entry does not redefine R.

For one configured partial percentage, each R trigger closes that percentage of the then-current volume. For multiple percentages, each percentage is based on the original managed volume. Every partial close is floored to the broker volume step rather than rounded to nearest: with current `0.05`, a 50% raw amount of `0.025` on a `0.01` step closes `0.02` and leaves `0.03`. Partial semantics always retain at least one broker minimum-volume remainder; if the position is already at the minimum (for example `0.01` when broker min is `0.01`), the partial is skipped. Explicit full-close actions and `InpCloseAtR` remain full-close semantics.

`InpManageMagic=-1` manages positions regardless of origin, including manual/mobile orders. Set a specific magic or `InpManagedSymbols` if the EA must not touch all positions on the account.

## Operational boundary

The PC may be shut down on weekends if no MT5 cloud work is expected. While the terminal is closed, MT5 bridge status is offline and no EA-side BE/partial/protection logic can run. Broker-native SL/TP already attached to positions remains active at the broker even when the PC is off.

Offline verification of the local failover code does not install the Windows Scheduled Task or perform a live Telegram handoff/Upstash outage simulation. Those are separate operator-authorized production steps; no broker mutation is required merely to validate failover ownership.

## NeoTech customer read-only connector

`OAK_NeoTech_ReadOnly_Connector.mq5` is the public/customer telemetry path for `/neotech`. It is intentionally separate from `OAK_Cloud_Manager_EA`: it contains no trading class, `OrderSend`, close, modify or delete path. Investor Password/read-only remains the recommended/default mode. A terminal logged in with Master Password is accepted only when its browser-created one-time pairing explicitly records `TRADING_CAPABLE_ACCEPTED`; a read-only pairing still fails closed if the terminal later gains trading permission.

Customer flow is three steps: choose Investor Password (recommended) or explicitly accept the Master Password warning on `/neotech`, download the compiled `OAK_NeoTech_ReadOnly_Connector.ex5`, add `https://www.oakgatekeeper.uk` to the MT5 WebRequest allow-list, then attach the EA with that one-time pairing code. Connector v1.0.4 stores credentials by broker/server/login identity and reloads the correct credential automatically when MT5 changes account. An account that has not been paired, or whose saved authorization no longer matches its trading capability, remains attached in a waiting state instead of unloading; pair/authorize that account once, then future switches reuse its credential automatically. If the web profile revokes or purges that connector, the server's 401 is treated as terminal for that credential: the matching local stale credential is cleared, sync stops in `WAITING_PAIR`, and a fresh pairing code can be entered in EA Properties without detaching/reattaching the EA. Revocation is never silently undone. Legacy login-only credentials migrate to the server-scoped file only after a successful sync. The matching `.mq5` source and SHA-256 manifest are published beside the compiled file for audit. No MT5 password is sent to OAK.

The connector receives one revocable 256-bit ingest token after pairing and stores it only inside the customer's MT5 Files area; the server stores only its SHA-256. Raw deal/cash-flow history is transmitted over HTTPS for server-side rule computation and is not retained as a database record. The retained cloud state is masked/fingerprinted account metadata, derived Visual Profile, bounded equity samples and scoped audit metadata with a 400-day maximum sliding retention. The `/neotech` UI can revoke connector access or immediately purge retained account/profile/equity/connector data.

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
