# OAK Manager User Guide (v3.17.0)

OAK Manager is a Windows command centre for multi-profile MT5 operations: monitor workers, Hidden SL/TP, copy trade, scheduled orders, Telegram, diagnostics, and the companion dashboard.

## Start

1. Configure `config.json` and `profiles.json` locally. Never commit tokens or broker credentials.
2. Start the NativeQt application and select a profile.
3. Start only the required workers from **Signals**.
4. Use **Diagnostics** to inspect the selected profile before placing orders.

## Signal engine

- Pattern source: `GBPUSD` M5/M30.
- Output/trade pairs: `XAUUSD`, `GBPAUD` at H=2/H=3, and the GBP group at H=9/H=14. H=12/H=13/H=15 may receive a no-gold label from the H=11 classification.
- Trading days: Monday to Friday. Weekend slots are off.
- Active slots: **H=2, H=3, H=4, H=5, H=7, H=8, H=9, H=11, H=12, H=13, H=14, H=15**. Live Telegram signals are sent at broker `:45`.
- Disabled slots: **H=6, H=10, H=17**.
- H=11 uses the four H=7–H=10 gold H1 candles for SW/BT classification.

### Core matrix

| Slot | Rule |
| --- | --- |
| H=2/H=3 | XAUUSD reverses the prior trading day's H=5; `GBPAUD` follows that prior H=5. |
| H=4/H=5/H=12/H=13/H=15 | M5/M30 + XAUUSD M30; H=4/H=5 retain internal direction markers. |
| H=7/H=8 | XAUUSD reverses today's H=5. H=8 is preferred when H=6 agrees with the derived direction; otherwise H=7 is preferred. No badge is shown when H=6 is missing/unresolved. |
| H=9 | The GBP group reverses the prior H=5; Friday follows it. |
| H=11 | SW/BT classification from the four XAUUSD H1 candles H=7–H=10; no BUY/SELL is emitted. |
| H=14 | The GBP group follows today's H=5; Friday reverses it. |

## Dashboard

- Production: https://oak-hidden-sltp-manager-dun.vercel.app
- Use the explicit **EN / VN** switch. News times are rendered in the viewer’s local system timezone, including daylight-saving changes.
- **History** retains H=11 and renders the four H1 candles as an OHLC SVG chart.
- The Fact Check page accepts pasted text, uploads, drag-and-drop, and clipboard images.

## Fact Check

Google and DuckDuckGo collect the evidence. AI is optional and only reviews that collected evidence; it never invents sources.

1. GitHub Models: `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`, or `gh auth token`.
2. OpenAI Responses API fallback: `FACTCHECK_AI_API_KEY`.

## Safety

- Telegram quick orders use `<lot> <broker HH:MM> <profile>` (for example `0.01 09:15 vantage`); execution time is independent of the signal H slot and is converted to the Windows clock before scheduling. `/pending` is created only after a valid user reply.
- A scheduled close with a time is queued, not executed immediately.
- Copy Trading guardrails, daily caps, and the kill switch are enforced by the worker.
- Treat every signal as decision support, not a trading guarantee.

## Packages

Download the installer, unpacked build, and source bundle from [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).
