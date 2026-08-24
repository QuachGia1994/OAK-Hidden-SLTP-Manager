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
