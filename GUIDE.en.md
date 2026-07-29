# OAK Manager User Guide (v3.18.2)

OAK Manager is a Windows command centre for multi-profile MT5 operations: monitor workers, Hidden SL/TP, copy trade, scheduled orders, Telegram, diagnostics, and the companion dashboard.

## Start

1. Configure `config.json` and `profiles.json` locally. Never commit tokens or broker credentials.
2. Start the NativeQt application and select a profile.
3. Start only the required workers from **Signals**.
4. Use **Diagnostics** to inspect the selected profile before placing orders.

## Signal engine

- Entry and signal sources are separate: M15 selects entry; each symbol's own H1 candles create its final direction.
- Outputs: `XAUUSD`, `GBPUSD`, `GBPAUD`, `GBPJPY`, and `GBPCAD` are evaluated independently.
- Trading days: Monday to Friday. Weekend slots are off.
- Active slots: **H=3, H=7, H=9, H=12, H=14, H=16**; each publishes at Broker `H:00`.
- Stage A uses XAUUSD M15 Base `H−00:30`, pattern `H−00:45/H−01:00/H−01:15`, and the XAUUSD `H−00:15` post-filter, then compares with GBPAUD M15 `H−00:15`; when needed, one GBPAUD M15 bar opening at `H:30` and closing at `H:45` selects `H:11`, `H:49`, or `(H+1):25`.
- H3 uses the previous Broker session's three H1 candles in order: C1/Base `04:00`, C2 `03:00`, C3 `02:00`. The eight-case three-candle matrix classifies SW/BT; SW reverses Base and BT keeps it.
- Thursday H3 recomputes the same week's Monday source: BT reuses Monday's direction; XAUUSD SW terminates H3 as `WAIT`, sends no tradable signal, and resumes from H7.
- H7/H9/H12/H14/H16 use four H1 candles from each symbol. `(H+1):25` selects C1 at `H:00`; `H:11/H:49` selects C1 at `H−1:00`. The exact ten-rule classifier derives SW/BT; then `H:11/H:49` reverses Signal Base, `(H+1):25` keeps it, and only `15:25`/`16:49` reverse once more.
- A missing candle or unresolved DOJI makes that symbol `WAIT`; an unclosed C1 is pending and retried only until entry.
- BrokerClock calibrates from a fresh live terminal tick and fails closed for stale, missing, or inconsistent observations; absolute UTC is separated from MT5 wall-clock data timestamps.

### Core matrix

| Slot | Rule |
| --- | --- |
| H=3 | C1/Base = previous-session H1 04:00, C2 = 03:00, C3 = 02:00; use the three-candle SW/BT matrix. Thursday uses Monday's source: keep BT, while XAUUSD SW makes the whole slot WAIT until H7. |
| H=7/H=9/H=12/H=14/H=16 | Each symbol uses entry-selected H1 C1..C4 and the ten-rule matrix. `H:11/H:49` reverse Signal Base; `(H+1):25` keeps it; only `15:25`/`16:49` reverse again. |

Stage A determines entry only; M15 direction is not the final signal. The Dashboard can open each symbol's H1 C1..C4 evidence (C1..C3 for H3).

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
