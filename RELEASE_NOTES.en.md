# RELEASE NOTES

## [v3.16.0+] - 2026-07-10
*Logic v10: H=14 slot removed from all signal calculations.*

### Signal rules (logic v10)
- Mon–Fri slots **H=3–13,15** (**no H=14**)
- No-gold: Thu H=3–4 + H≥12; Fri H=3–11 (trade gold Fri H=12,15 only)
- H=3–4: GA/GJ Buy/Sell vs gold; H=5+ Focus (Fri H=9+ GA+GJ only)
- pair_dirs: GBP map **only H=3–4**; **H=5+ XAU only**
- Removed: H=9/11/12 matrix · D-direction · **H=14**

## [v3.16.0] - 2026-07-10
*Signal rules v9 + multi-monitor isolation + EN docs + installer package.*

### Signal rules (logic v9, superseded)
- Earlier band included H=14; see v3.16.0+ / logic v10.

### Multi-monitor
- Concurrent workers; Running Monitors panel
- Exact `--profile` orphan kill (Vantage ≠ VantageDemo)
- Per-profile `trades_*.json` and `pending_partials_*.json`
- Reader threads never touch Tk; Account card uses hb_profile prefix

### i18n
- Guide / README / Release Notes load `.en.md` when language = EN
- Signal card Buy / Sell / No trade labels localized

### Packaging
- App version **v3.16.0**
- Installer.exe, window-unpack.zip, OAK Source zip

## [v3.15.2] - 2026-07-09
Earlier schedule/profile safety, Thursday W1 notes, Telegram 409 mitigations. Superseded signal details live in v3.16.0.
