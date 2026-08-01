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
- **Layers 2–3 — XAUUSD Entry Plan:** H3/H7/H9/H12/H14 classify two three-candle M30 groups: Layer 2 `H−00:30/H−01:00/H−01:30` → BT `H:11`; SW opens Layer 3 `H:00/H−00:30/H−01:00` → SW `H:49`, BT `(H+1):25`, with H3 `04:25`. H16 uses its independent XAUUSD H1 groups: Layer 2 `05:00/04:00/03:00` → `16:11`; if SW, Layer 3 `10:00/09:00/08:00` → BT `16:49`, SW `17:25`.
- **Layer 1 — Reference Signal:** once the Entry Plan resolves, `H:11` / `(H+1):25` combines GBPUSD D with the common Day Mode: the same branch keeps D and a different branch reverses it. `H:49` is the exception: it reverses the immediately prior completed XAUUSD H1 candle.
- **Pair derivation:** XAUUSD and GBPUSD share Layer 1's Reference Signal. GBPAUD follows on same D and reverses on opposite D; GBPJPY/GBPCAD apply the inverse relation.
- **Layer 4 — Final Reverse:** applies exactly once after pair derivation.
- D-Direction is independent for all five symbols from the previous-session H4 candle opened at `20:00` Broker. Missing/DOJI data returns `WAIT`; there is no MT5 candle fallback.
- MT4 heartbeat supplies the Broker Clock. MT5 execution loss only disables execution; stale/disconnected MT4 data fails the Signal closed.
- The MT5 execution gateway persists v87 idempotency intents; it sends orders only when the profile explicitly sets `signal_execution_enabled=true` (or `SIGNAL_BOT_EXECUTION_ENABLED=true`).

### MT4 Feed v87 setup

1. Start the MT4 Feed Server first and set the v87 `MT4_Data_Feeder.mq4` `FeedBaseURL` input to `http://127.0.0.1/mt4-feed` (default HTTP port 80). Allow `http://127.0.0.1` in MT4 **WebRequest** permissions. Port `:5001` remains local health/management only.
2. The EA can attach to **any chart** to persist raw bars: it reads `Symbol()`, accepts broker prefixes/suffixes, and normalizes a safe key; no manual `SymbolName` exists. The v87 Signal core still requires XAUUSD (or GOLD), GBPUSD, GBPAUD, GBPJPY, and GBPCAD to be attached.
3. The legacy `http://127.0.0.1:5000/mt4_data` endpoint and an EA with `ServerURL`, `BrokerName`, `SymbolName`, and `MagicNumber` inputs are pre-v87 and must be replaced.

### Core matrix

| Slot | Rule |
| --- | --- |
| H=3/H=7/H=9/H=12/H=14 | XAU M30 Layer 2 BT → `H:11`; SW → Layer 3 SW `H:49` or BT `(H+1):25` (H3 `04:25`). |
| H=16 | XAU H1 Layer 2 BT → `16:11`; Layer 2 SW + Layer 3 BT → `16:49`; Layer 3 SW → `17:25`. |

The Dashboard opens XAUUSD M30 evidence for both layers, their SW/BT groups, the two candidates, and the final entry. GBP signals remain independent rows.

## Dashboard

- Production: https://oak-hidden-sltp-manager-dun.vercel.app
- Use the explicit **EN / VN** switch. News times are rendered in the viewer’s local system timezone, including daylight-saving changes.
- All v87 weekday slots are active, including special and post-special sessions. `WAIT` is reserved for missing MT4 data or unresolved DOJI.
- The Fact Check page accepts pasted text, uploads, drag-and-drop, and clipboard images.

## Fact Check

Google and DuckDuckGo collect the evidence. AI is optional and only reviews that collected evidence; it never invents sources.

1. GitHub Models: `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`, or `gh auth token`.
2. OpenAI Responses API fallback: `FACTCHECK_AI_API_KEY`.

## Safety

- Telegram quick orders use `<lot> <broker HH:MM> <profile>` (for example `0.01 09:15 vantage`); execution time is independent of the signal H slot and is converted to the Windows clock before scheduling. `/pending` is created only after a valid user reply.
- A scheduled close with a time is queued, not executed immediately.
- The signal bot does not create an Auto-Close schedule. The existing manual Copy Trade **Close All** path and existing **Auto Closed Opposite** path remain unchanged.
- Copy Trading guardrails, daily caps, and the kill switch are enforced by the worker.
- Treat every signal as decision support, not a trading guarantee.

## Packages

Download the installer, unpacked build, and source bundle from [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).
