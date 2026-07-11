# OAK Hidden SLTP Manager (v3.16.0)

Windows desktop app for multi-process MT5 management: monitoring, Hidden SL/TP, Ghost Mode, signal bot, Telegram bridge, and web dashboard.

Related docs:
- [GUIDE.en.md](GUIDE.en.md) · [GUIDE.md](GUIDE.md) (Vietnamese)
- [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md)

## Features

### Desktop
- Hidden SL/TP (optional Visible SL/TP)
- Auto Partial by R + volume %, Auto BE with buffer
- Multi-profile + multi-monitor workers
- Ghost Mode (human simulation when algo is blocked)
- Pending/scheduled orders, Diagnostics, debug bundle export
- In-app docs: Guide / README / Release Notes (VN + EN)

### Signal bot
- Pairs: XAUUSD, GBPAUD, GBPCAD, GBPUSD, GBPJPY
- Slots: Mon–Fri H=2–13 and H=15
- H=2 uses the normal M5/M30 signal only; GBPAUD and GBPJPY are opposite gold, with no H1 gold check
- No-gold: Mon H=5–11; Thu H=3–4; Fri H=3–11 (gold Fri only H=12–13 and H=15)
- Tue–Wed: H=3–4 focus GBPAUD + GBPJPY opposite gold; H=5–8 focus GBPAUD; H=9/11/12/15 focus the full GBP group
- Thu: H=5–8 focus GBPAUD; H=9/11/12/15 focus the full GBP group
- Fri: no GBP Focus
- Monday focuses GBPUSD+GBPCAD only at H=9; other Monday hours have no GBP Focus
- D-direction removed

### Safety
- Exact profile match on Telegram commands
- Atomic schedule claim; one worker per profile
- Exact orphan kill by `--profile` argument

## Windows packages
- [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases)
