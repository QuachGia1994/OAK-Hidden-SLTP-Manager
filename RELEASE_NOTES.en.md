# RELEASE NOTES

## [v3.16.1] - 2026-07-11
*Weekend signal card fix, doc refresh, backup script refresh, and release packaging sync.*

### Desktop signal card
- Sat/Sun now shows `Current: No trade`
- Weekend pair labels are cleared
- Weekend `Next` and `Countdown` no longer point to an old weekday slot

### Docs
- README / Guide / Release Notes updated to match the live app behavior
- Installation doc refreshed for the current package names and build outputs
- Signal matrix rewritten around the active H=2-15 logic and weekend handling

### Backup + packaging
- App version bumped to **v3.16.1**
- `create_backup_final.py` now includes the `scripts/` folder in the source zip
- Backup exclusions now ignore common local cache folders

## [v3.16.0] - 2026-07-10
*Signal rules v9 + multi-monitor isolation + EN docs + installer package.*

### Signal rules (logic v9)
- Mon-Fri slots H=2-15
- H=2 uses M5/M30 only; GBPAUD + GBPJPY are opposite gold without an H1 gold check
- No-gold: Mon H=3-11; Thu H=3-4
- Friday no longer uses no-gold labels; H=3-7 and H=9-10 reverse signal to gold
- Focus: Tue-Wed H=3-4 GA+GJ opposite gold, H=5-8 GA, H=9/11/12/15 full group; Thu H=5-8 GA and H=9/11/12/15 full group; Fri no GBP focus
- `pair_dirs`: GBP map only at H=2-4; H=5+ is XAU only
- Removed: H=9/11/12 direction matrix and all D-direction plumbing

### Multi-monitor
- Concurrent workers; Running Monitors panel
- Exact `--profile` orphan kill (Vantage != VantageDemo)
- Per-profile `trades_*.json` and `pending_partials_*.json`
- Reader threads never touch Tk; Account card uses `hb_profile` prefix

### i18n
- Guide / README / Release Notes load `.en.md` when language = EN
- Signal card Buy / Sell / No trade labels localized

### Packaging
- App version **v3.16.0**
- Installer.exe, window-unpack.zip, OAK Source zip
