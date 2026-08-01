# OAK Manager User Guide (v3.18.2)

OAK Manager is a Windows command centre for multi-profile MT5 operations: monitor workers, Hidden SL/TP, copy trade, scheduled orders, Telegram, diagnostics, and the companion dashboard.

## Start

1. Configure `config.json` and `profiles.json` locally. Never commit tokens or broker credentials.
2. Start the NativeQt application and select a profile.
3. Start only the required workers from **Signals**.
4. Use **Diagnostics** to inspect the selected profile before placing orders.

## Signal engine

- MT4 Feed is the sole market-data and Broker-clock authority; MT5 is execution/account/position only.
- Outputs: `XAUUSD`, `GBPUSD`, `GBPAUD`, `GBPJPY`, and `GBPCAD`; all five share one XAUUSD Entry Plan while direction remains pair-specific.
- Trading days: Monday to Friday. Weekend slots are off.
- Active slots: **H=3, H=7, H=9, H=12, H=14, H=16**; each publishes at Broker `H:00`.
- H3/H7/H9/H12/H14 use two three-candle XAUUSD M30 layers: Layer 2 `H−00:30/H−01:00/H−01:30` → BT `H:11`; SW moves to Layer 3 `H:00/H−00:30/H−01:00` → SW `H:49`, BT `(H+1):25`, with H3 `04:25`.
- H16 uses independent XAUUSD H1 layers: `05:00/04:00/03:00` → BT `16:11`; SW then `10:00/09:00/08:00` → BT `16:49`, SW `17:25`.
- GBPUSD is the Reference Signal and XAUUSD is locked to it. GBPAUD follows/reverses by D relation; GBPJPY/GBPCAD apply the inverse relation. Final Reverse runs exactly once.
- D-Direction is independent for all five symbols from the previous-session H4 candle opened at `20:00` Broker. Missing/DOJI data returns `WAIT`; there is no MT5 candle fallback.
- MT4 heartbeat supplies the Broker Clock. MT5 execution loss only disables execution; stale/disconnected MT4 data fails the Signal closed.
- The MT5 execution gateway persists v87 idempotency intents; it sends orders only when the profile explicitly sets `signal_execution_enabled=true` (or `SIGNAL_BOT_EXECUTION_ENABLED=true`).

### Core matrix

| Slot | Rule |
| --- | --- |
| H=3/H=7/H=9/H=12/H=14 | XAU M30 Layer 2 BT → `H:11`; SW → Layer 3 SW `H:49` or BT `(H+1):25` (H3 `04:25`). |
| H=16 | XAU H1 Layer 2 BT → `16:11`; Layer 2 SW + Layer 3 BT → `16:49`; Layer 3 SW → `17:25`. |

The Dashboard opens XAUUSD M30 evidence for both layers, their SW/BT groups, the two candidates, and the final entry. GBP signals remain independent rows.

## Dashboard

- Production: https://oak-hidden-sltp-manager-dun.vercel.app
- Use the explicit **EN / VN** switch. News times are rendered in the viewer’s local system timezone, including daylight-saving changes.
- `deactivated` signals are reference-only, visually muted, and excluded from the current actionable signal.
- The Fact Check page accepts pasted text, uploads, drag-and-drop, and clipboard images.

## Fact Check

Google and DuckDuckGo collect the evidence. AI is optional and only reviews that collected evidence; it never invents sources.

1. GitHub Models: `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`, or `gh auth token`.
2. OpenAI Responses API fallback: `FACTCHECK_AI_API_KEY`.

## Safety

- Telegram quick orders use `<lot> <broker HH:MM> <profile>` (for example `0.01 09:15 vantage`); execution time is independent of the signal H slot and is converted to the Windows clock before scheduling. `/pending` is created only after a valid user reply.
- A scheduled close with a time is queued, not executed immediately.
- The signal bot does not create an Auto-Close schedule; users manage closing positions manually.
- Copy Trading guardrails, daily caps, and the kill switch are enforced by the worker.
- Treat every signal as decision support, not a trading guarantee.

## Packages

Download the installer, unpacked build, and source bundle from [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).
