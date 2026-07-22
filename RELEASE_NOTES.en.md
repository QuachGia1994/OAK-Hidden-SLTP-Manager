# RELEASE NOTES

## [Unreleased] - 2026-07-22

- Retain valid H=11 SW/BT records with all four candles in seven-day history so the Dashboard can render the OHLC SVG.
- Make H=7/H=8 priority symmetric for either H=5 direction and avoid fabricating a badge when the H=6 candle is unavailable.
- Accept full broker `HH:MM` values in Telegram quick orders, convert them to the Windows clock, and retain legacy minute-only input; `/pending` is created only after a valid user reply.

## [v3.17.0] - 2026-07-18

### Signal matrix

- Unified live calculation and seven-day rebuild through one slot-matrix entry point.
- Active slots are H=2, H=3, H=4, H=5, H=7, H=8, H=9, H=12, H=13, and H=15. H=6/H=10/H=11/H=14/H=17 are off.
- H=2 applies M5/M30 then the XAUUSD M30 post-process; Thursday reuses Monday H=2 and reverses only in special-calendar weeks. The Friday H=2 reversal rule has been removed completely, so Friday always uses the standard flow.
- H=3/H=7 reverse final H=2. H=8/H=9/H=12/H=13/H=15 keep the standard M5/M30 + XAUUSD M30 flow.

### NativeQt command center

- Refined the Dark, Deep Sea, and Contrast skin tokens for a coherent desktop surface.
- Deep Sea now uses cyan for selected profiles, running cards, positive actions, and combo-box selection instead of inheriting Dark mint.
- Added the NativeQt window icon and expanded EN/VN coverage across the shell.

### Reliability and packaging

- Fixed the `d_direction` NameError that stopped the MT5 Signal Bot after history rebuild.
- Made the domain layer lazy so NativeQt starts without loading MetaTrader5 or numpy; the frozen installer now passes a real startup smoke test.
- Bundled the design guidance and third-party notice with the lightweight NativeQt package.
- Removed obsolete build artifacts and dead legacy launcher files from the project tree.
- Raised the release version to **v3.17.0**.

## [v3.16.5] - 2026-07-16

- Historical signal-matrix adjustments, superseded by the v3.17.0 matrix above.

## [v3.16.3] - 2026-07-13

### Signal matrix

- Simplified output/list pairs to `XAUUSD` and removed obsolete GBP focus badges.
- Earlier slot-matrix iterations are superseded by v3.17.0.

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
