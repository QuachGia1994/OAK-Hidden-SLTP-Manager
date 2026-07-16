# RELEASE NOTES

## [v3.16.4] - 2026-07-16

### Signal matrix

- **H=2 on Tuesday and Thursday no longer reverses XAU** (keeps normal pattern).
- H=2 reverse remains only on Friday special-calendar weeks.
- Notes updated in bot, reminders, dashboard day rules, README, and Guide (logic v18).

## [v3.16.3] - 2026-07-13

### Signal matrix

- Simplified the signal matrix to XAU-only: output/list pairs now contain only `XAUUSD`.
- Active slots are Monday-Friday H=2-10, H=12-13, H=15 plus H=17; H=11/H=14 are disabled.
- H=2 weekday reverse matrix (later revised in v3.16.4).
- Removed all no-gold labels.
- Removed all GBP pair lists/focus badges from core logic, Dashboard, and Telegram notes.
- Removed broad Friday XAU reversal logic while keeping the special-calendar Friday H=2 reversal.
- H=4 D-direction and H=17 D-direction preview are documented as active.

### Packaging

- Bumped app version to **v3.16.3**.
- Refreshed README / Guide / Release Notes and source backup defaults for the current signal engine.

## [v3.16.2] - 2026-07-12

### Dashboard + i18n

- Removed System mode from the language switcher; EN / VN now keeps a single active state.
- Cleaned Fact Check English/Vietnamese rendering across result cards, stats, sources, verdicts, and AI panels.
- Prevented old cached English AI summaries from leaking into the Vietnamese UI.

### Fact Check

- Added GitHub Models as the default AI review path using an existing GitHub token.
- Kept OpenAI Responses API support as a fallback.
- AI now receives an explicit output language and must review only collected Google/DDG evidence.
- Added tests for Vietnamese and unaccented Vietnamese AI output-language detection.

### Packaging

- Bumped app version to **v3.16.2**.
- Refreshed README / Guide / Release Notes for the current app behavior.
- Updated `create_backup_final.py` source packaging exclusions and essentials.

## [v3.16.1] - 2026-07-11

- Fixed weekend desktop signal card: no stale current signal, next slot, countdown, or pair labels.
- Refreshed docs and backup packaging script.
- Synced release package naming.

## [v3.16.0] - 2026-07-10

- Added signal rules v9, multi-monitor isolation, bilingual docs, and installer packaging.
- Added profile-safe worker shutdown and per-profile runtime files.
