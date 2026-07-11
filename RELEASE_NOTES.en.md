# RELEASE NOTES

## [v3.16.0] - 2026-07-10
*Signal rules v9 + multi-monitor isolation + EN docs + installer package.*

### Signal rules (logic v9)
- Mon–Fri slots H=3–15
- No-gold: Thu H=3–4; Fri H=3–11 (trade gold Fri H=12–15 only)
- Focus: H=3–8 GA+GJ; H=9/11/12/14/15 full group (Fri: GA+GJ only)
- pair_dirs: GBP map **only H=3–4**; **H=5+ XAU only** (Focus has no Buy/Sell dims)
- Removed: H=9/11/12 direction matrix and all D-direction plumbing
- Full matrix table in `GUIDE.en.md` / `GUIDE.md`

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
