# OAK MANAGER User Guide (v3.16.0)

This guide covers the desktop app, signal bot, Telegram bridge, and web dashboard.

## 1. Quick start

1. Create `config.json` with `telegram_token`, `telegram_chat_id`, `mt5_path`, `dashboard_url`, `dashboard_api_key`
2. Install deps: `pip install -r requirements.txt`
3. Run `CHAY_ROBOT.bat`
4. Open the app, pick a profile, then use the **Signals** tab to start needed processes

## 2. Desktop tabs

### Dashboard
- Select profile, Start/Stop monitor(s)
- Multi-monitor panel: live workers with PID + Stop
- MT5 / Telegram / Ghost / System status bar
- Account + Signal cards, news, console filters

### Signals
Four background processes: MT5 Signal Bot, MT4-MT5 Server, MiMo Telegram Bot, MiMo Worker.

### Profiles / Copy Trading / Pending / Diagnostics
Profile CRUD, master/slave copy, scheduled entries, log viewer + debug bundle.

## 3. Signal rules (logic v9)

### Pairs
`XAUUSD`, `GBPAUD`, `GBPCAD`, `GBPUSD`, `GBPJPY`

### Slot schedule
| Day | Hours |
| --- | --- |
| Mon–Fri (T2–T6) | H=3..15 at :45 broker |
| Weekend | none |

### No-gold label (XAU)
| Day | No-gold | Trade gold |
| --- | --- | --- |
| Mon (T2) | H=5–11 | H=3–4,12–15 |
| Tue–Wed | none | H=3–15 |
| Thu (T5) | H=3–4 | H=5–15 |
| Fri (T6) | H=3–11 | H=12–15 only |

### GBP display
| Hours | Display | Mon–Thu | Friday |
| --- | --- | --- | --- |
| H=3–4 | **Buy/Sell vs gold** (not Focus) | GA opposite gold, GJ same gold | No GBP |
| H=5–8 | Focus only | GA + GJ | No GBP Focus |
| H=9,11,12,14,15 | Focus only | Full GBP group | No GBP Focus |

### pair_dirs mapping
| Hours | Content |
| --- | --- |
| H=3–4 | XAU + GJ same gold, GA opposite, GU/GC `--` |
| H=5+ | **XAU only** (GBP = Focus list only) |

### Quick matrix

| H | GBP UI T2–T5 | GBP UI T6 | pair_dirs GBP | XAU T2–T4 | XAU T5 | XAU T6 |
| --- | --- | --- | --- | --- | --- | --- |
| 3–4 | Dir vs gold | No GBP | Map vs XAU | Trade | No-gold | No-gold |
| 5–8 | No GBP Focus | No GBP Focus | **None** (XAU only) | No-gold | Trade | No-gold |
| 9 | Focus GBPUSD+GBPCAD | No GBP Focus | None | No-gold | Trade | No-gold |
| 11 | No GBP Focus | No GBP Focus | None | No-gold | Trade | No-gold |
| 10,13 | — | — | None | Trade | Trade | No-gold |
| 12 | Full 4 | GA+GJ | None | Trade | Trade | Trade |
| 14–15 | Full 4 | GA+GJ | None | Trade | Trade | Trade |


**Removed:** H=9/11/12 direction matrix · D-direction.

### XAU M30 flip
- Same direction as M30 → flip XAU; else follow M30
- H=3–4: rebuild GBP from final XAU
- H=5+: update XAU only

## 4. Multi-monitor
- Concurrent workers; exact `--profile` orphan kill
- Per-profile `trades_*.json` / `pending_partials_*.json`
- Stop dialog shows Profile / PID / Account

## 5. Web dashboard
URL: https://oak-hidden-sltp-manager-dun.vercel.app

## 6. Telegram
Exact profile targeting on schedule commands; NLP + slash commands for status, pending, closeall, etc.
