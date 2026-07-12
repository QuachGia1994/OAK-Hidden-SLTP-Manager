# OAK MANAGER User Guide (v3.16.2)

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

`XAUUSD`, `GBPAUD`, `GBPCAD`, `GBPUSD`, `GBPJPY`

### Rhythms

| Rhythm | Hours | Label |
| --- | --- | --- |
| 0 | H=2 | XAU |
| 1 | H=3-4 | JPY |
| 2 | H=5-8 | AUD |
| 3 | H=9-11 | GBP |
| 4 | H=12-14 | EUR |
| 5 | H=15 | USD |

### Schedule

| Day | Active hours |
| --- | --- |
| Monday-Friday | H=2-15 at broker `:45` |
| Saturday-Sunday | none |

### No-gold label

| Day | No-gold hours |
| --- | --- |
| Monday | H=3-15 |
| Tuesday-Wednesday | H=9-11 |
| Thursday | H=3-4, H=12-15 |
| Friday | none |

### GBP focus

| Day | Rule |
| --- | --- |
| Monday | H=9 focuses GBPUSD + GBPCAD only |
| Tuesday-Wednesday | H=3-4 GBPAUD + GBPJPY opposite gold; H=5-8 GBPAUD; H=9/10/11/12/13/15 full GBP group; H=14 no GBP focus |
| Thursday | H=3-4 no GBP focus; H=5-8 GBPAUD; H=9/10/11/12/13/15 full GBP group; H=14 no GBP focus |
| Friday | No GBP focus |

### Gold calculation notes

- H=2 uses M5/M30 only and skips H1 gold.
- GBPAUD and GBPJPY are opposite gold when direction is assigned.
- Friday reverses the calculated signal back to gold at H=3-7 and H=9-10.
- D-direction and the old H=9/11/12 direction matrix are removed.

## 4. Web dashboard

Production URL: https://oak-hidden-sltp-manager-dun.vercel.app

- Language switch: System / EN / VN.
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
