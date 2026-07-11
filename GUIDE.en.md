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
| Mon–Fri (T2–T6) | H=3–13 and H=15 at :45 broker |
| Weekend | none |

### No-gold label (XAU)
| Day | No-gold | Trade gold |
| --- | --- | --- |
| Mon (T2) | H=5–11 | H=3–4, H=12–13, H=15 |
| Tue–Wed | none | H=3–13, H=15 |
| Thu (T5) | H=3–4 | H=5–13, H=15 |
| Fri (T6) | H=3–11 | H=12–13, H=15 only |

### GBP display
| Hours | Display | Mon–Thu | Friday |
| --- | --- | --- | --- |
| H=3–4 | **Buy/Sell vs gold** (not Focus) | Tue–Wed: GA + GJ opposite gold | No GBP Focus |
| H=5–8 | Focus only | Tue–Wed and Thu: GBPAUD | No GBP Focus |
| H=9 | Focus only | Mon: GBPUSD + GBPCAD; Tue–Thu: full GBP group | No GBP Focus |
| H=11,12,15 | Focus only | Tue–Thu: full GBP group | No GBP Focus |

### pair_dirs mapping
| Hours | Content |
| --- | --- |
| H=3–4 | Tue–Wed: XAU + GA/GJ opposite; other days XAU only |
| H=5+ | **XAU only** (GBP = Focus list only) |

### Quick matrix

| H | Mon GBP | Tue–Wed GBP | Thu GBP | Fri GBP | XAU rules |
| --- | --- | --- | --- | --- | --- |
| 3–4 | No Focus | GA+GJ opposite gold | No Focus | No Focus | Thu/Fri no-gold |
| 5–8 | No Focus | GBPAUD | GBPAUD | No Focus | Mon/Fri no-gold |
| 9 | GBPUSD+GBPCAD | Full group | Full group | No Focus | Mon/Fri no-gold |
| 10 | No Focus | No Focus | No Focus | No Focus | Mon/Fri no-gold |
| 11 | No Focus | Full group | Full group | No Focus | Mon/Fri no-gold |
| 12–13 | No Focus | Full group at H=12 | Full group at H=12 | No Focus | Trade gold |
| 15 | No Focus | Full group | Full group | No Focus | Trade gold |


**Removed:** H=9/11/12 direction matrix · D-direction.

### XAU M30 flip
- Same direction as M30 → flip XAU; else follow M30
- H=3–4: rebuild GBP from final XAU
- H=5+: update XAU only; GBP Focus has no direction

## 4. Multi-monitor
- Concurrent workers; exact `--profile` orphan kill
- Per-profile `trades_*.json` / `pending_partials_*.json`
- Stop dialog shows Profile / PID / Account

## 5. Web dashboard
URL: https://oak-hidden-sltp-manager-dun.vercel.app

## 6. Telegram
Exact profile targeting on schedule commands; NLP + slash commands for status, pending, closeall, etc.
