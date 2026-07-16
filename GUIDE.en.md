# OAK MANAGER User Guide (v3.16.3)

This guide covers the desktop app, signal bot, Telegram bridge, Fact Check worker, and web dashboard.

## 1. Quick start

1. Create `config.json` with `telegram_token`, `telegram_chat_id`, `mt5_path`, `dashboard_url`, and `dashboard_api_key`.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run `CHAY_ROBOT.bat`.
4. Open the desktop app, select a profile, then use **Signals** to start or stop the background services.

## 2. Desktop tabs

### Dashboard

- Select profile and start/stop MT5 monitors.
- See running monitor PID, account, signal, news, and activity logs.
- Weekend signal card stays empty: no current signal, next slot, countdown, or stale pair labels.

### Signals

`START ALL` / `STOP ALL` controls:

- MT5 Signal Bot
- MT4-MT5 Server
- MiMo Telegram Bot
- MiMo Worker
- Fact Check Worker

### Profiles / Copy Trading / Pending / Diagnostics

Manage profiles, copy-trading settings, scheduled entries, log filters, and debug bundle export.

## 3. Signal rules

### Pairs

`XAUUSD`

### Rhythms

| Rhythm | Hours | Label |
| --- | --- | --- |
| 0 | H=2 | XAU |
| 1 | H=3-4 | JPY |
| 2 | H=5-8 | AUD |
| 3 | H=9-10 | XAU |
| 4 | H=12-13 | EUR |
| 5 | H=15, H=17 | USD |

### Schedule

| Day | Active hours |
| --- | --- |
| Monday-Friday | H=2-10, H=12-13, H=15, H=17 at broker `:45` |
| Saturday-Sunday | none |

### Pair output

- XAUUSD only.
- No-gold labels have been fully removed.
- GBP pair lists/focus badges have been fully removed.

### Gold calculation notes

- H=2 uses the `GBPUSD` M5/M30 pattern source, keeps XAUUSD M30 post-processing, and skips H1 gold.
- H=2 on **Tuesday and Thursday does not reverse XAU** (normal pattern).
- H=2 Friday is normally XAU-only; special-calendar weeks reverse XAU.
- Friday has no broad XAU reversal on other hours.
- H=4 stores D-direction in the same direction as XAUUSD for every trading day.
- H=17 displays XAUUSD from the stored H=4 D-direction.
- The old H=9/12 direction matrix is removed, and H=11/H=14 are disabled in core rules.

## 4. Web dashboard

Production URL: https://oak-hidden-sltp-manager-dun.vercel.app

- Language switch: EN / VN.
- Signal cards, history, news, and rules are localized.
- Fact Check supports pasted text, uploaded images, dropped images, and clipboard images.

## 5. Fact Check

Fact Check uses DuckDuckGo + Google evidence search. AI review is optional and must only evaluate collected evidence.

AI configuration priority:

1. GitHub Models through `FACTCHECK_GITHUB_TOKEN`, `GITHUB_TOKEN`, `GH_TOKEN`, or `gh auth token`.
2. OpenAI Responses API through `FACTCHECK_AI_API_KEY`.

The default GitHub Models preview model is `openai/gpt-4.1-mini`.

## 6. Telegram

Telegram commands target the exact profile. Schedule claims are atomic so only one worker handles a pending order.
