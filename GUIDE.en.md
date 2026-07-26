# OAK Manager User Guide (v3.17.0)

OAK Manager is a Windows command centre for multi-profile MT5 operations: monitor workers, Hidden SL/TP, copy trade, scheduled orders, Telegram, diagnostics, and the companion dashboard.

## Start

1. Configure `config.json` and `profiles.json` locally. Never commit tokens or broker credentials.
2. Start the NativeQt application and select a profile.
3. Start only the required workers from **Signals**.
4. Use **Diagnostics** to inspect the selected profile before placing orders.

## Signal engine

- Pattern source: `GBPUSD` M5/M30.
- Output/trade pairs: `XAUUSD`, `GBPAUD` at H=3, and the GBP group at H=9/H=14.
- Trading days: Monday to Friday. Weekend slots are off.
- Active slots: **H=3, H=4, H=5, H=6, H=9, H=12, H=14, H=16**.
- Broker publication: H3 `03:00`; H4 `04:45`; H5 `05:45`; H6 `06:00`; H9 `09:00` (`08:00` on special days); H12 `12:00`; H14 `14:00`; H16 `16:00`.
- Entry: H3 `03:11/03:49`; H4 `04:45`; H5 `05:45`; H6 `06:11`; H9 `09:49` (`08:30` on special days); H12 `12:11`; H14 `14:15/14:49`; H16 `16:11/16:49`.
- Special and post-special days do not generate H12/H14/H16; special-Thursday H3 is retained only as `deactivated`. A Thursday/Friday pair spanning New Year is not special.

### Core matrix

| Slot | Rule |
| --- | --- |
| H=3 | XAUUSD reverses the prior trading day's H5; Thursday reuses Monday H3. `GBPAUD` opposes XAUUSD. |
| H=4/H=5 | GBPUSD M5/M30 pattern combined with XAUUSD M30. |
| H=6/H=9 | Four-H1 grouping with weekday and special-day reversals. H9 also emits GBPUSD and GBPAUD. |
| H=12/H=14 | Reverse H4, then apply weekday and four-H1 reversals. Four-M30 data only controls priority/entry and completeness; priority applies Tuesday through Thursday only. H14 also emits GBPUSD and GBPAUD. |
| H=16 | Selects the priority H6–H12 or H9–H14 branch; missing dependencies produce `WAIT`. |

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
