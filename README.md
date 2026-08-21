# ROBOT SLTP Pro / OAK Gatekeeper

ROBOT SLTP now treats cloud H1 scanning and Telegram command/control as the maintained trading surfaces. The old Engine5/Pattern5 H4 stack has been retired from runtime, web, desktop, tests and publishing.

## Maintained surfaces

1. **OAK Gatekeeper Web** (`dashboard/`) — production web shell at `https://www.oakgatekeeper.uk`.
   - `/engine`: current-broker-day H1 scanner signals only.
   - cTrader OAuth/token vault and read-only account/session APIs.
   - Telegram cloud webhook/control APIs.
2. **Desktop Tauri** (`robot-sltp-pro/`) — fallback/local workstation for MT5 profile observation, SLTP configuration, local pending-task management and runtime diagnostics. It is no longer required for the production H1 scanner or Telegram webhook.
3. **Python runtime** (`domain/`, `services/`, root scripts) — local fallback worker and MT5 utilities. Local scanner ownership is fallback-only while cloud scanner is primary.

## H1 scanner v6

Cloud profile: `cTrader IcMarkets`.

The scanner reads only closed H1 candles from the current broker day, H03 through H17. Pattern detection uses exactly two source charts:

- `AUDUSD` pattern source for `XAUUSD` output.
- `GBPUSD` pattern source for `EURUSD`, `AUDUSD`, `USDCAD`, `USDJPY` outputs.

At scanner slot `Hn`, the base candle is always the closed `H(n-1)` candle:

- `XAUUSD`: base = `GBPUSD H(n-1)`.
- Other outputs: base = that target symbol's own `H(n-1)`.
- `T` (close > open) → BUY; `G` → SELL.

Pattern groups, newest → oldest:

- `TG` / `GT` → `SW 2 cây` → keep the base signal.
- `TGG` / `GTT` → `SW 3 cây thuần` → reverse the base signal.
- `TGT` / `GTG` → `SW 3 cây xen kẽ` → keep the base signal.
- `TGTG` / `GTGT` → `SW 4 cây xen kẽ` → keep the base signal.

At one slot, the longest exact match wins: 4-candle before 3-candle before 2-candle. Missing source/base H1 data fails closed; there is no previous-day or other-timeframe fallback.

Production flow:

`GitHub Actions H:00 → Vercel /api/h1-scanner/run → cTrader JSON/WebSocket H1 → scanner v6 → Telegram + Upstash → /engine`

The route retries briefly after H:00 if cTrader has not finalized the just-closed H1 candle yet. Redis state/lock prevents replay and overlapping cloud scans.

## Telegram cloud control

Production webhook:

`https://www.oakgatekeeper.uk/api/telegram/webhook`

Maintained cloud commands include status/profile/position inspection, pending-intent management and `/del ID` / `/del all`. Telegram update IDs are idempotently claimed in Upstash. The desktop receiver checks Telegram `getWebhookInfo` and exits when cloud webhook ownership is active, so opening the desktop does not steal the bot.

cTrader OAuth remains `accounts` scope and broker access is read-only. Cloud Telegram intents that would mutate broker state remain fail-closed/approval-required; no automatic order/open/close/SLTP mutation is part of the maintained cloud path.

## H1 parity utilities

The retained parity stack is H1-only:

- `robot-sltp-pro/ctrader_h1_market_data.py`
- `robot-sltp-pro/ctrader_snapshot_cli.py`
- `robot-sltp-pro/mt5_h1_snapshot_cli.py`
- `robot-sltp-pro/h1_market_data.py`
- `robot-sltp-pro/h1_market_data_parity_cli.py`

Parity compares broker-day H1 timestamps and T/G direction. OHLC differences are diagnostic only because scanner semantics consume candle direction, not exact prices.

## Build and verification

Python:

```bash
pip install -r requirements.txt
python -m pytest tests -q
python robot-sltp-pro/test_backend_bridge.py
```

Web:

```bash
npm --prefix dashboard ci
npm --prefix dashboard run test
npm --prefix dashboard run build
```

Desktop frontend:

```bash
npm --prefix robot-sltp-pro ci
npm --prefix robot-sltp-pro run build
```

Rust/Tauri:

```bash
cargo check --locked --manifest-path robot-sltp-pro/src-tauri/Cargo.toml
```

## Security boundaries

- Never commit MT5, Telegram, cTrader or VIP credentials/tokens.
- cTrader refresh/access tokens remain encrypted server-side with AES-256-GCM.
- H1 scanner cloud stays on `accounts` OAuth scope.
- Missing/ambiguous market data fails closed.
- Desktop MT5 observation is attach-only unless the user explicitly starts local runtime.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the maintained ownership map and cloud H1 details.
