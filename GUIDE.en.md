# OAK MANAGER User Guide (v3.16.1)

This guide covers the desktop app, signal bot, Telegram bridge, and web dashboard.

## 1. Quick start

1. Create `config.json` with `telegram_token`, `telegram_chat_id`, `mt5_path`, `dashboard_url`, `dashboard_api_key`
2. Install deps: `pip install -r requirements.txt`
3. Run `CHAY_ROBOT.bat`
4. Open the app, pick a profile, then use the **Signals** tab to start the required processes

## 2. Desktop tabs

### Dashboard
- Select profile, Start/Stop monitor(s)
- Multi-monitor panel: live workers with PID + Stop
- MT5 / Telegram / Ghost / System status bar
- Account + Signal cards, news, console filters
- Sat/Sun signal card shows `Current: No trade`, with empty pair labels, `Next`, and `Countdown`

### Signals
Four background processes: MT5 Signal Bot, MT4-MT5 Server, MiMo Telegram Bot, MiMo Worker.

### Profiles / Copy Trading / Pending / Diagnostics
Profile CRUD, master/slave copy, scheduled entries, log viewer, and debug bundle export.

## 3. Signal rules (logic v9)

### Pairs
`XAUUSD`, `GBPAUD`, `GBPCAD`, `GBPUSD`, `GBPJPY`

### Slot schedule
| Day | Hours |
| --- | --- |
| Mon-Fri | H=2-13 and H=15 at :45 broker |
| Weekend | none |

### No-gold label (XAU)
| Day | No-gold | Trade gold |
| --- | --- | --- |
| Mon | H=3-11 | H=2, H=12-13, H=15 |
| Tue-Wed | none | H=2-13, H=15 |
| Thu | H=3-4 | H=2, H=5-13, H=15 |
| Fri | H=3-11 | H=2, H=12-13, H=15 |

### GBP display
| Hours | Display | Mon | Tue-Wed | Thu | Fri |
| --- | --- | --- | --- | --- | --- |
| H=2 | Buy/Sell vs gold | GA + GJ opposite gold | GA + GJ opposite gold, reversed XAU signal | GA + GJ opposite gold, reversed XAU signal | GA + GJ opposite gold |
| H=3-4 | Buy/Sell vs gold | No focus | GA + GJ opposite gold | No focus | No focus |
| H=5-8 | Focus only | No focus | GBPAUD | GBPAUD | No focus |
| H=9 | Focus only | GBPUSD + GBPCAD | Full group | Full group | No focus |
| H=10 | Focus only | No focus | No focus | No focus | No focus |
| H=11 | Focus only | No focus | Full group | Full group | No focus |
| H=12 | Focus only | No focus | Full group | Full group | No focus |
| H=13 | Focus only | No focus | No focus | No focus | No focus |
| H=15 | Focus only | No focus | Full group | Full group | No focus |

### pair_dirs mapping
| Hours | Content |
| --- | --- |
| H=2 | XAU + GBPAUD/GBPJPY opposite gold; GBPUSD/GBPCAD stay `--` |
| H=3-4 | Tue-Wed: XAU + GBPAUD/GBPJPY opposite gold; other days XAU only |
| H=5+ | XAU only (GBP is displayed through Focus only) |

### XAU M30 flip
- Same direction as M30 -> flip XAU
- Different from M30 -> keep XAU
- H=2 and Tue-Wed H=3-4 rebuild GBP from final XAU
- H=5+ updates XAU only; GBP Focus has no direction

### Removed
- H=9/11/12 direction matrix
- D-direction

## 4. Multi-monitor
- Concurrent workers; exact `--profile` orphan kill
- Per-profile `trades_*.json` / `pending_partials_*.json`
- Stop dialog shows Profile / PID / Account

## 5. Web dashboard
URL: https://oak-hidden-sltp-manager-dun.vercel.app

## 6. Telegram
Exact profile targeting on schedule commands; NLP + slash commands for status, pending, closeall, and other workflow helpers.
