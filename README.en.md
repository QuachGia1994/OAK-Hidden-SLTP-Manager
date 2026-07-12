# OAK Hidden SLTP Manager (v3.16.1)

Windows desktop app for multi-process MT5 management: monitoring, Hidden SL/TP, Ghost Mode, signal bot, Telegram bridge, and web dashboard.

Related docs:
- [GUIDE.en.md](GUIDE.en.md) · [GUIDE.md](GUIDE.md) (Vietnamese)
- [RELEASE_NOTES.en.md](RELEASE_NOTES.en.md)

## Features

### Desktop
- Hidden SL/TP with optional Visible SL/TP
- Auto Partial by R + volume %, Auto BE with buffer
- Multi-profile + multi-monitor workers
- Ghost Mode
- Pending/scheduled orders, Diagnostics, debug bundle export
- In-app docs: Guide / README / Release Notes (VN + EN)

### Signal bot
- Pairs: XAUUSD, GBPAUD, GBPCAD, GBPUSD, GBPJPY
- Slots: Mon-Fri H=2-15
- Weekend: no trading slots
- H=2 uses M5/M30 only; GBPJPY/GBPAUD are opposite gold, no H1 gold check
- No-gold: Mon H=3-15, Tue-Wed H=9-11, Thu H=3-4
- Fri: H=3-7 and H=9-10 reverse signal to gold; no no-gold label
- Mon: H=9 focuses GBPUSD + GBPCAD; other Monday hours no GBP focus
- Tue-Wed: H=3-4 GBPJPY + GBPAUD opposite gold; H=5-8 GBPAUD; H=9/10/11/12/13/15 full GBP group; H=14 XAU only
- Thu: H=3-4 no GBP focus; H=5-8 GBPAUD; H=9/10/11/12/13/15 full GBP group; H=14 XAU only
- Fri: no GBP focus
- D-direction removed

### Desktop signal card
- Sat/Sun now shows `Current: No trade`
- Pair labels are cleared on weekends
- `Next` and `Countdown` stay blank on weekends instead of carrying an old weekday slot

### Safety
- Exact profile match on Telegram commands
- Atomic schedule claim; one worker per profile
- Exact orphan kill by `--profile` argument

## Windows packages
- [GitHub Releases](https://github.com/QuachGia1994/OAK-Hidden-SLTP-Manager/releases)
