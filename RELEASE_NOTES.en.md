# RELEASE NOTES

## Unreleased
- Fixed browser Fact Check requests returning HTTP 401 without exposing the internal dashboard API key
- Added Fact Check Worker to desktop START ALL / STOP ALL and frozen-app process mode
- Added Google News fallback, optional AI evidence review, adaptive multi-pass OCR, and clipboard image paste

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
- H=2 uses M5/M30 only; GBPJPY/GBPAUD are opposite gold without an H1 gold check
- No-gold: Mon H=3-15, Tue-Wed H=9-11, Thu H=3-4
- Fri reverses signal to gold at H=3-7 and H=9-10, with no no-gold label
- Focus is GBP-only display after H=5; D-direction removed

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
