# OAK Manager User Guide (v3.18.1)

OAK Manager is a Windows command centre for multi-profile MT5 operations: monitor workers, Hidden SL/TP, copy trade, scheduled orders, Telegram, diagnostics, and the companion dashboard.

## Start

1. Configure `config.json` and `profiles.json` locally. Never commit tokens or broker credentials.
2. Start the NativeQt application and select a profile.
3. Start only the required workers from **Signals**.
4. Use **Diagnostics** to inspect the selected profile before placing orders.

## Signal engine

- Signal source: two `GBPUSD` H1 bars from yesterday; two `GBPAUD` H1 bars are comparison-only. `XAUUSD` M15 selects entry time only.
- Output/trade pair: `XAUUSD` only.
- Trading days: Monday to Friday. Weekend slots are off.
- Active slots: **H=3, H=4, H=6, H=9, H=12, H=14, H=16**.
- Broker publication: H3 `03:00`; H4 `04:00`; H6 `06:00`; H9 `09:00`; H12 `12:00`; H14 `14:00`; H16 `16:00`.
- Every H=3/4/6/9/12/14/16 slot publishes at `H:00`. Read the two completed `GBPUSD` H1 bars from yesterday immediately before the equivalent logical slot (for example, H9 today uses yesterday H8 and H7; H8 is the base). Opposite H1 bars are BT and keep the base direction; same-direction H1 bars are SW and reverse the base direction. This is the final XAUUSD signal.
- Repeat the calculation for the equivalent two `GBPAUD` H1 bars from yesterday only for comparison. Matching GBPUSD and GBPAUD results → entry `H:11`; differing results → classify today's three completed XAUUSD M15 bars after skipping the immediately preceding bar with the existing SW/BT table (H9 skips `08:45` and uses `08:30`/`08:15`/`08:00`): SW → `(H+1):25`, BT → `H:49`; H3 is the exception: SW → `04:49`, BT → `03:49`.
- H3 is always `deactivated` every Thursday. H4 is always `deactivated`/`DO NOT ENTER`, calculation/reference-only. A missing candle or unresolved DOJI at any step returns `WAIT`.
- BrokerClock calibrates from a fresh live terminal tick and fails closed for stale, missing, or inconsistent observations; absolute UTC is separated from MT5 wall-clock data timestamps.

### Core matrix

| Slot | Rule |
| --- | --- |
| H=3 | Uses the same two-H1 GBPUSD rule from yesterday; every Thursday it is `deactivated`. When the two GBP results differ, M15 SW enters `04:49`, BT enters `03:49`. |
| H=4 | Uses the same two-H1/M15 rule but is always `deactivated`/`DO NOT ENTER`; calculation/reference-only. |
| H=6/H=9/H=12/H=14/H=16 | Emits XAUUSD only. The final signal comes from yesterday's two GBPUSD H1 bars; GBPAUD is entry-time comparison only. |

When the GBP results match, every slot uses entry `H:11`. When they differ, classify today's three completed XAUUSD M15 bars after skipping the immediately preceding bar with the SW/BT table (H9 skips `08:45` and uses `08:30`/`08:15`/`08:00`): SW → `(H+1):25`, BT → `H:49`; H3 is the exception SW → `04:49`, BT → `03:49`. An unresolved DOJI or missing candle returns `WAIT`.

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
