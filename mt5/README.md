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
- Entry netting policy: scheduled same-direction milestones roll the existing TP instead of opening another position; XAU/GOLD advances by 20.0 price units and FX by 50 pips. Opposite direction still closes opposite positions and removes opposite pending orders before a new entry. EA v1.13 preserves the v1.12 projected post-net exposure preflight and `REVERSAL_INCOMPLETE` evidence.
- Break-even at configurable R with optional point offset.
- Full close at configurable R (`InpCloseAtR`).
- R-level partial closes using `InpPartialRLevels` and `InpPartialPercents`.
- Dynamic partial by floating profit or absolute price.
- Per-position management state persists in MT5 terminal Global Variables using `POSITION_IDENTIFIER`.
- Runtime identity is derived locally from terminal login/server. Blank `InpLocalProfile` becomes `local_<login>`; blank `InpLocalProviderAccountId` becomes deterministic `mt5:<sha256-32>`.
- Broker mutations pass through a durable FILE_COMMON per-origin claim/result ledger. A retained result is reconciled without re-execution; a retained claim without a result is `UNCERTAIN` and is never replayed automatically.
- Market entry waits up to 2.5 seconds for symbol synchronization and a usable bid/ask before building the broker request. Opposite-side settlement has a separate `InpEntryNetSettleTimeoutMs` guard (default 5000ms, clamped 1000..15000ms). There is no blind broker retry after an ambiguous transport result.
- EA v1.06 removed all cloud bridge settings from MT5 Properties and stopped cloud polling from `OnTimer`.
- EA v1.07 lowers the local FILE_COMMON poll default to `100ms` and makes all partial closes round DOWN to broker volume step while always retaining at least one broker minimum-volume remainder.
- EA v1.08 adds internal `entry_prepare`: it preserves opposite-position/pending cleanup, exposure/lot/symbol/tick guards and absolute SL/TP calculation, then returns exact fields for the controller. EA v1.12 additionally returns net-mutation/current-exposure evidence. EA v1.13 changes only the due scheduled same-direction case: when exactly one same-direction position is still open, it preserves SL, advances the current TP by one fixed step and returns a durable `tpRolled` result instead of submitting another Buy/Sell. If netting changed exposure but the replacement UI order is not submitted, the controller reports `REVERSAL_INCOMPLETE`, requires manual broker inspection, and never auto-replays the order. Immediate entries and all management actions remain EA-executed. No global mouse or keyboard injection is used.
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
6. Configure SL/TP, netting, BE/R and exposure guards as required. `InpEntryNetSettleTimeoutMs` defaults to 5000ms; increase it only for a demonstrably slower broker/terminal because timeout extension does not replace the `REVERSAL_INCOMPLETE` safety path.
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

Customer flow is three steps: choose Investor Password (recommended) or explicitly accept the Master Password warning on `/neotech`, download the compiled `OAK_NeoTech_ReadOnly_Connector.ex5`, add `https://www.oakgatekeeper.uk` to the MT5 WebRequest allow-list, then attach the EA with that one-time pairing code. Connector v1.0.5 stores credentials by broker/server/login identity and reloads the correct credential automatically when MT5 changes account. Its balance cash-flow classifier is conservative: only explicit deposit/fund/top-up or withdraw/payout comments are emitted as DEPOSIT/WITHDRAWAL; ambiguous balance adjustments are emitted as OTHER. An account that has not been paired, or whose saved authorization no longer matches its trading capability, remains attached in a waiting state instead of unloading; pair/authorize that account once, then future switches reuse its credential automatically. If the web profile revokes or purges that connector, the server's 401 is treated as terminal for that credential: the matching local stale credential is cleared, sync stops in `WAITING_PAIR`, and a fresh pairing code can be entered in EA Properties without detaching/reattaching the EA. Revocation is never silently undone. Legacy login-only credentials migrate to the server-scoped file only after a successful sync. The matching `.mq5` source and SHA-256 manifest are published beside the compiled file for audit. No MT5 password is sent to OAK.

The connector receives one revocable 256-bit ingest token after pairing and stores it only inside the customer's MT5 Files area; the server stores only its SHA-256. Raw deal/cash-flow history is transmitted over HTTPS for server-side rule computation and is not retained as a database record. The retained cloud state is masked/fingerprinted account metadata, derived Visual Profile, bounded equity samples and scoped audit metadata with a 400-day maximum sliding retention. The `/neotech` UI can revoke connector access or immediately purge retained account/profile/equity/connector data.

## NeoTech C5 reminder EA - auxiliary, read-only

`OAK_NeoTech_Compliance_EA.mq5` keeps its legacy filename so existing MT5 installation paths remain stable, but it is no longer a standalone compliance auditor. It is limited to C5 discipline helpers. v1.10 keeps the standalone v1.09 behavior and moves the chart `C5 LOOK` control to a safe upper-left chart anchor with chart-resize relayout so MT5's upper-right EA/status chrome cannot cover it. After a new eligible Forex/XAUUSD opening episode, it calculates the current effective NeoTech session and earliest next session/time, shows one simple local reminder when no matching Telegram controller is available, and the `C5 LOOK` button lists unique canonical symbols already opened in the current session. If an existing OAK Local Telegram controller heartbeat matches the active account, the EA forwards the same C5 reminder and publishes the tiny `/look` snapshot through the retained FILE_COMMON path.

The 14-rule NeoTech table is owned by `OAK_NeoTech_ReadOnly_Connector.mq5` plus the dashboard NeoTech engine. Do not add report formulas, FDD reconstruction, `/check`, direct Telegram polling or other compliance analytics back into this EA.

### Public download

The `/neotech` page offers `dashboard/public/downloads/OAK-NeoTech-C5-Setup.exe` as the default one-click Windows path plus the direct `OAK_NeoTech_Compliance_EA.ex5`, bilingual guide and SHA-256 manifests. Setup is a small .NET Framework Windows executable that embeds the verified EX5, scans `%APPDATA%\MetaQuotes\Terminal\*` data folders, installs only `MQL5\Experts\OAK_NeoTech_Compliance_EA.ex5`, and verifies the written hash. It does not install Node, Scheduled Tasks, Telegram credentials, WebRequest settings or trading-control components. Version 1.10 is the current published package: MetaEditor reported 0 errors, 0 warnings, X64 Regular for the EA. The public EX5 is 63,192 bytes with SHA-256 `3c4cb1850d51edbdbdc31de4bb15e7ad5842db6ebf246fc4bc22cb79bd1a172b`. The current Setup EXE is 72,704 bytes with SHA-256 `3ee9284536dd0cef6d768606da1281988f9981924ed813bbc3f9d48d98039f49`. The EX5, Setup and both SHA-256 manifests were rebuilt together from the v1.10 source.

Telegram is optional. Local popup + chart `C5 LOOK` require only the EA and do not depend on a controller, bot token, Node, PowerShell command, WebRequest allow-list or bootstrap. v1.10 continues to read the active MT5 login/server on every timer cycle and automatically follows account switches. When an already-provisioned OAK Local Telegram controller on the same PC exposes a fresh matching heartbeat, the EA uses the retained FILE_COMMON event/snapshot channel automatically. New controller provisioning remains an Advanced/Operator workflow documented by `local-failover/README.md`; it is not part of public C5 setup.

### Runtime flow

```text
New eligible MT5 opening episode
-> C5-only EA
-> NeoTech session/next-entry calculation
-> matching Telegram controller present? FILE_COMMON event -> Telegram reminder
-> otherwise local MT5 popup

Trader clicks C5 LOOK
-> same C5-only EA
-> current NeoTech session window + unique opening-episode symbols
-> local MT5 popup

Every timer tick, when a matching Telegram controller is present
-> current session snapshot
-> account-fenced FILE_COMMON look snapshot
-> Telegram /look
```

The EA remains broker-read-only. It reads deal/position metadata and local controller heartbeat files only. It contains no `OrderSend`, `CTrade`, close, modify, delete, approve or schedule path.

### Inputs

1. `InpTimerSeconds` - helper timer interval, default 2 seconds, valid 1-60.
2. `InpStartupCatchupMinutes` - optional recent-open-position recovery after attach/restart or an account switch, default 30 minutes, valid 0-120.
3. `InpLocalPopup` - standalone C5 popup fallback when no matching Telegram controller is available, default `true`.
4. `InpLookButton` - show the chart `C5 LOOK` button, default `true`.

No account/login input is required. v1.10 keeps the active normalized login/server as its runtime identity; when either changes it clears account-scoped reminder/dedupe memory and catch-up scans the new account. No Telegram bot token, chat/user ACL, webhook setting, WebRequest allow-list, profile slug, history lookback, FDD or SL/TP audit input is required. If Telegram is used, the local controller remains the sole bot owner and keeps its token outside MT5.

### C5 semantics

- Eligible products: broker metadata must classify the symbol as Forex or XAU/USD. Broker aliases such as `GOLD` resolve through currency metadata to canonical `XAUUSD` when the broker exposes `XAU`/`USD` correctly.
- Session basis: NeoTech server-local time with UTC+2 in November-March and UTC+3 in April-October.
- Overlap priority: Asia -> Europe -> US, so overlap remains assigned to the earlier session.
- Reminder time: displayed in Vietnam UTC+7 plus the NeoTech server time/offset.
- Same-position scale-in fills are not treated as a fresh opening episode. A reversal (`DEAL_ENTRY_INOUT`) starts a new episode.
- Opening outside Asia/Europe/US is fail-closed: Telegram shows `C5: KHÔNG XÁC MINH` and does not invent a next-entry permission.
- Startup catch-up only considers currently open positions whose current episode began inside the configured recent window.

### Delivery and dedupe

For optional Telegram delivery, the EA matches the current MT5 login/server against a fresh `OAKLocalFailover/status_*.json` heartbeat and reuses that heartbeat's `profile` and `providerAccountId`. On an MT5 account switch it automatically resets the previous account's transient queue/dedupe state and rebinds to the new login/server without re-entering Properties. When that heartbeat is present, it persists an immutable `neotech_c5_reentry` event under MT5 `FILE_COMMON`; the local controller validates the same account identity and delivers the text through its existing durable notification ledger. When no matching controller is present, v1.10 delivers the reminder locally instead of withholding C5 functionality.

Event IDs are deal-scoped (`neotech_c5:<deal-ticket>`). Duplicate MT5 callbacks are suppressed in-memory. Local standalone reminders are emitted once per observed opening episode; Telegram delivery uses the existing controller ledger when the controller is available.

For `/look`, the EA rewrites `look_<profile>_<login>.json` every timer tick with `session`, Vietnam session start/end and the unique canonical symbols whose opening episode began inside that active session. The local controller accepts only a fresh snapshot whose profile/provider/login/server still matches the fresh MT5 heartbeat. A closed trade remains listed until the session ends; same-position scale-ins/partial fills do not create a new opening occurrence. Outside Asia/Europe/US the snapshot explicitly reports `OUTSIDE_SESSION`.

### Verification

`tests/NeoTechC5ReminderSyntheticTests.mq5` covers summer/winter session transitions, current-session windows, US -> next-day Asia, outside-session refusal, Vietnam-time conversion, Telegram wording, standalone local reminder wording, local `C5 LOOK` wording and heartbeat JSON parsing. Compile both the EA and this script with MetaEditor and require `0 errors, 0 warnings`. `OAK-NeoTech-C5-Setup.exe --dry-run --quiet` is the non-mutating installer smoke check; it must validate the embedded EX5 checksum and discover at least one MT5 data folder on the test PC.

The former MQL5 14-rule compliance core/JSON modules and 59-fixture auditor suite were intentionally removed. Public NeoTech analytics tests now assert that the connector/dashboard keep the 14-rule contract while this auxiliary EA stays C5-reminder-only.
