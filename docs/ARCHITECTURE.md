# ROBOT SLTP / OAK Gatekeeper Architecture

This document describes the maintained production surfaces after retiring the Engine5/Pattern5 H4 stack.

## Product surfaces

- `dashboard/`: Next.js cloud control plane and web UI.
- `robot-sltp-pro/`: Tauri desktop fallback/diagnostic workstation.
- `domain/`, `services/`, root Python: local fallback runtime and MT5 utilities.

## Ownership map

| Concern | Canonical owner | Consumers |
| --- | --- | --- |
| H1 scanner v7 pattern/signal semantics | `dashboard/src/lib/h1-cloud-scanner.ts` | cloud scanner route, tests |
| Cloud H1 market-data transport | `dashboard/src/lib/ctrader-json.ts` | `/api/h1-scanner/run`, read-only account status |
| Cloud scanner orchestration/state/Telegram publication | `dashboard/src/app/api/h1-scanner/run/route.ts` | GitHub H:00 scheduler |
| Public H1 transport contract | `dashboard/src/lib/h1-signals.ts` | `/engine` server page and H1 UI |
| H1 web rendering/detail | `dashboard/src/components/H1EngineBoard.tsx`, `H1SignalBoard.tsx` | browser |
| VIP H1 redaction | `dashboard/src/lib/vip.ts` | `/engine` server page |
| Telegram cloud command parsing | `dashboard/src/lib/telegram-cloud-domain.ts` | Telegram webhook |
| Telegram cloud intent/audit/idempotency store | `dashboard/src/lib/telegram-cloud-store.ts` | webhook, due tick |
| Telegram cloud webhook | `dashboard/src/app/api/telegram/webhook/route.ts` | Telegram Bot API |
| Telegram due-intent notification | `dashboard/src/app/api/telegram/tick/route.ts` | GitHub OIDC scheduler |
| cTrader OAuth/token vault | `dashboard/src/app/api/ctrader/*`, `dashboard/src/lib/ctrader-vault.ts` | scanner, read-only Telegram status/positions |
| Local fallback H1 scanner | `domain/xau_h1_pattern_scanner.py` | `MonitorWorker` when explicitly run locally |
| Local fallback H1 public publisher | `domain/h1_signal_public_feed.py` | Upstash H1 feed |
| Desktop IPC/runtime | `robot-sltp-pro/backend_bridge.py`, `src/backend-client.ts` | Tauri UI |
| MT5 attach/start safety | `services/mt5_service.py`, `services/mt5_terminal_service.py` | local observation/fallback runtime |
| H1 parity | `robot-sltp-pro/h1_market_data.py` + H1 snapshot CLIs | migration/regression only |

## H1 scanner v7

The production scanner is cloud-primary and operates only on H1 data for the current broker day.

### Pattern sources

Only two charts are pattern scanners:

- `AUDUSD` → pattern source for `XAUUSD` output.
- `GBPUSD` → pattern source for `EURUSD`, `AUDUSD`, `USDCAD`, `USDJPY` outputs.

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

Source transform:

- `sw2`: keep base.
- `sw3Pure`: reverse base.
- `sw3Normal`: reverse base.

There is no target-side post-check. Every accepted `sw3Pure` alert is marked `/!\\` in Telegram and the web cell. If another `sw3Pure` appears exactly two slots after the previous accepted pure, that second slot is skipped completely and pure tracking resets from the next slot. Example: H04 + H06 pure => H06 is omitted and scanning starts fresh from H07; H06 + H08 pure => H08 is omitted and scanning starts fresh from H09.

No day classification, Pattern5 group, H4 block, previous-day fallback, or cross-timeframe fallback exists in this scanner.

### Time and replay behavior

- Eligible scan slots: H03 through H17.
- GitHub scheduled trigger starts at minute `58`, waits inside the runner until the next exact `H:00` boundary, then requests OIDC and calls the private Vercel route. This avoids GitHub's normal top-of-hour scheduler congestion while keeping GitHub as a secret-free trigger.
- If GitHub itself starts the scheduled job after the boundary, the route catch-up logic runs immediately; GitHub Actions is therefore best-effort timing rather than a hard real-time clock.
- Vercel retries briefly when the just-closed H1 candle is not yet visible from cTrader.
- Redis NX/EX lock prevents overlapping cloud invocations.
- Cloud state schema is v7. Older public feeds are not reinterpreted; pre-cutover slots are suppressed through the current broker hour to prevent replay under changed semantics, and current-day web history is rebuilt from current H1 data without resending Telegram alerts.
- Telegram must acknowledge a new signal before the alert is persisted.
- Public Upstash H1 feed is schema v7; skipped paired-pure slots never enter state/feed/Telegram/web.
- There is no target-side post-check, STOP-H17 overlay, day classification, Pattern5 block, or H4 dependency.

The local Python fallback mirrors the same v7 source/base transform and paired-pure reset semantics.

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

Maintained management/read commands include `/status`, `/profiles`, `/positions`, `/pending`, `/del ID`, `/del all`, plus intent capture for entry/close/modify requests.

cTrader remains OAuth scope `accounts` and the selected account remains read-only. Broker-mutating intents are not automatically executed by the maintained cloud path. Due scheduler notifications are authenticated by GitHub OIDC and do not mutate broker state.

`oak_enginecore.py` is fallback-only. It calls Telegram `getWebhookInfo` before acquiring its local singleton lock and exits when the cloud webhook is active; it never deletes/steals the cloud webhook merely because desktop is opened.

## Desktop fallback

The desktop no longer contains Engine5/Pattern5 UI or commands. It remains useful for:

- observing configured MT5 profiles;
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
- Cloud webhook active → local Telegram receiver exits instead of racing it.

## Verification ownership

- Scanner semantics: `dashboard/src/lib/h1-cloud-scanner.test.ts`, `tests/test_xau_h1_pattern_scanner.py`.
- Public H1 contract: `dashboard/src/lib/h1-signals.test.ts`, `tests/test_h1_signal_public_feed.py`.
- Telegram cloud control: `dashboard/src/lib/telegram-cloud-domain.test.ts`, `telegram-cloud-route.test.ts`.
- cTrader H1/parity: `tests/test_h1_market_data.py` and snapshot/parity CLIs.
- Desktop bridge/runtime lifecycle: `robot-sltp-pro/test_backend_bridge.py`, runtime lifecycle tests.
