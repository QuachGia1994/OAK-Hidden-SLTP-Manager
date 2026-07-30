# OAK Manager User Guide (v3.18.2)

OAK Manager is a Windows command centre for multi-profile MT5 operations: monitor workers, Hidden SL/TP, copy trade, scheduled orders, Telegram, diagnostics, and the companion dashboard.

## Start

1. Configure `config.json` and `profiles.json` locally. Never commit tokens or broker credentials.
2. Start the NativeQt application and select a profile.
3. Start only the required workers from **Signals**.
4. Use **Diagnostics** to inspect the selected profile before placing orders.

## Signal engine

- Four GBP directions are independently derived from each symbol's own M30 candles. XAUUSD direction follows GBPAUD, while XAUUSD entry is selected by two XAUUSD M30 layers.
- Outputs: `XAUUSD`, `GBPUSD`, `GBPAUD`, `GBPJPY`, and `GBPCAD`; every symbol has its own entry field in records/API payloads.
- Trading days: Monday to Friday. Weekend slots are off.
- Active slots: **H=3, H=7, H=9, H=12, H=14, H=16**; each publishes at Broker `H:00`.
- GBP signals use four M30 close times `H−00:30/H−01:00/H−01:30/H−02:00`; the newest candle is Base. The ten-rule matrix classifies SW/BT; SW reverses Base and BT keeps Base.
- XAU Layer 1 creates two entry candidates and Layer 2 selects the final result. H3 uses Layer 1 `02:30/02:00/01:30` and Layer 2 `03:00/02:30/02:00/01:30`; other slots use two four-candle windows separated by 30 minutes.
- XAU entry: `SW+SW → H:49`, `SW+BT → (H+1):25` (H3 uses `04:49`), `BT+SW → H:11`, and `BT+BT → H:49`. All four GBP entries are the next full Broker hour after the XAU entry.
- XAUUSD starts from the final GBPAUD Signal: H3/H14/H16 reverse it; H7/H9/H12 keep it unchanged. XAU layer results never change direction.
- A missing candle, invalid OHLC, or DOJI makes the affected Signal/Layer `WAIT`; H1, M15, and other symbols are never fallbacks.
- BrokerClock calibrates from a fresh live terminal tick and fails closed for stale, missing, or inconsistent observations; absolute UTC is separated from MT5 wall-clock data timestamps.

### Core matrix

| Slot | Rule |
| --- | --- |
| H=3 | GBP Signal uses the shared four-M30 rule. XAU L1 is `02:30/02:00/01:30`; XAU L2 is `03:00/02:30/02:00/01:30`. The late branch is `04:49`. XAU reverses the GBPAUD Signal. |
| H=7/H=9/H=12 | Two XAU M30 layers separated by 30 minutes; the late branch is `(H+1):25`. XAU keeps the GBPAUD Signal unchanged. |
| H=14/H=16 | Two XAU M30 layers separated by 30 minutes; the late branch is `(H+1):25`. XAU reverses the GBPAUD Signal. |

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
- The signal bot closes every `XAUUSD*` position at `17:59` Broker and every `GBPAUD*`, `GBPCAD*`, `GBPJPY*`, and `GBPUSD*` position at `19:59` Broker. This intraday rule intentionally does not filter by profile, magic number, or comment.
- Copy Trading guardrails, daily caps, and the kill switch are enforced by the worker.
- Treat every signal as decision support, not a trading guarantee.

## Packages

Download the installer, unpacked build, and source bundle from [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).
