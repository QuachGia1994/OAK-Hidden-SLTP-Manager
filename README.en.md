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
- H=2 uses M5/M30 only; GBPAUD and GBPJPY are opposite gold, with no H1 gold check
- Tue/Thu H=2 reverses the XAU signal after the M5/M30 calculation
- No-gold: Mon H=3-15, Tue-Wed H=9-11, Thu H=3-4
- Fri: H=3-7 and H=9-10 reverse signal to gold; no no-gold label
- Tue-Wed: H=3-4 show GBPAUD + GBPJPY opposite gold; H=5-8 focus GBPAUD; H=9/10/11/12/13/15 focus the full GBP group; H=14 stays XAU-only
- Thu: H=3-4 no GBP focus; H=5-8 focus GBPAUD; H=9/10/11/12/13/15 focus the full GBP group; H=14 stays XAU-only
- Fri: no GBP focus
- Mon: H=9 focuses GBPUSD + GBPCAD only; other Monday hours have no GBP focus
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
