# OAK Manager User Guide (v3.17.0)

OAK Manager is a Windows command centre for multi-profile MT5 operations: monitor workers, Hidden SL/TP, copy trade, scheduled orders, Telegram, diagnostics, and the companion dashboard.

## Start

1. Configure `config.json` and `profiles.json` locally. Never commit tokens or broker credentials.
2. Start the NativeQt application and select a profile.
3. Start only the required workers from **Signals**.
4. Use **Diagnostics** to inspect the selected profile before placing orders.

## Signal engine

- Pattern source: `GBPUSD` M5/M30.
- Output/trade pair: `XAUUSD` only. There are no GBP focus lists and no no-gold labels.
- Trading days: Monday to Friday. Weekend slots are off.
- Active slots at broker `:45`: **H=2, H=3, H=4, H=5, H=7, H=8, H=9, H=12, H=13, H=15**.
- Disabled slots: **H=6, H=10, H=11, H=14, H=17**.
- H1 gold is not used.

### Core matrix

| Slot | Rule |
| --- | --- |
| H=2 | Calculate the M5/M30 pattern, then apply the XAUUSD M30 post-process. Thursday reuses Monday H=2 and reverses only in special-calendar weeks. Friday always uses the standard flow with no separate reversal rule. |
| H=3, H=7 | Reverse the final XAUUSD H=2 direction. |
| H=4 | Normal M5/M30 + XAUUSD M30. Its D-direction is stored internally. |
| H=5, H=8, H=9, H=12, H=13, H=15 | Normal M5/M30 + XAUUSD M30. |

The special-calendar reversal is evaluated only for Thursday H=2. A week is special when its Wednesday is day 30 or 1, or its Friday is day 3, 4, or 7; this condition never reverses Friday H=2.

## Dashboard

- Production: https://oak-hidden-sltp-manager-dun.vercel.app
- Use the explicit **EN / VN** switch. News times are rendered in the viewer’s local system timezone, including daylight-saving changes.
- The Fact Check page accepts pasted text, uploads, drag-and-drop, and clipboard images.

## Fact Check

Google and DuckDuckGo collect the evidence. AI is optional and only reviews that collected evidence; it never invents sources.

1. GitHub Models: `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`, or `gh auth token`.
2. OpenAI Responses API fallback: `FACTCHECK_AI_API_KEY`.

## Safety

- Scheduled Telegram commands are scoped to the exact profile.
- A scheduled close with a time is queued, not executed immediately.
- Copy Trading guardrails, daily caps, and the kill switch are enforced by the worker.
- Treat every signal as decision support, not a trading guarantee.

## Packages

Download the installer, unpacked build, and source bundle from [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases).
