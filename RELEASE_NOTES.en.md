# RELEASE NOTES

## [v3.18.2] - 2026-07-28

- Replace the complete signal matrix with one rule for H=3/H=4/H=6/H=9/H=12/H=14/H=16: derive XAUUSD from the two equivalent-slot GBPUSD H1 candles on the previous Broker day, using GBPAUD only as the comparison branch for entry selection.
- Matching derived directions enter at `H:11`. Opposite directions classify today's three XAUUSD M15 candles after skipping the immediately preceding bar; for H=9 this skips 08:45 and uses exactly 08:30/08:15/08:00 to choose `H:49` or `(H+1):25` (03:49/04:49 for H=3).
- Keep fail-closed behavior for missing candles or unresolved DOJI, emit XAUUSD only, retain H=4 and Thursday H=3 as `deactivated`, and remove H=5 together with retired M30/4H1/priority/RHYTHM logic.
- Raise the signal contract to logic version 49 and synchronize the bot, MT4/MT5 comparator, desktop, API, Dashboard, documentation, and regression tests so stale records cannot enter the current UI.

## [v3.18.1] - 2026-07-26

- Standardize reference-only states: H=3 is always `deactivated` every Thursday; H=4/H=5 are always `deactivated`, intermediate-only dependencies and never actionable signals.
- Correct normal-session priority: Monday/Friday use BT → H12 and SW → H14; Tuesday/Wednesday/Thursday use SW → H12 and BT → H14. Special Thu/Fri and post-special Monday continue to suppress H12/H14/H16.
- Replace D1-only inference with BrokerClock calibration from a fresh live tick, failing closed on stale, missing, or inconsistent observations; separate scheduling/UI absolute UTC from MT5 wall-clock data timestamps.
- Synchronize README/Guide, reminder, and Dashboard Rules text with the v3.18.1 contract.

## [v3.18.0] - 2026-07-26

- Standardize the active logical slots as H=3, H=4, H=5, H=6, H=9, H=12, H=14, and H=16; separate publication from entry time and remove all legacy H=2/H=11/H=13/H=15/H=1500 paths.
- Retry delayed candles only until entry, prevent restart catch-up/duplicates, keep a single 45-day startup rebuild, and return `WAIT` for missing candles or unresolved DOJI data.
- Normalize special Thursday–Friday pairs while excluding 31 December 2026–1 January 2027; persist special-Thursday H=3 as `deactivated` and fully suppress H=12/H=14/H=16 on special/post-special days.
- Use one fail-closed Broker clock inferred from MT5 D1 candles per date and publish its canonical time fields to the worker, desktop app, and Dashboard.
- Make Signal Bot the sole owner of close-ALL at 17:59 for XAUUSD and 19:59 for the GBP group, with position verification and restart-safe retries; Copy Trade Manager retains manual scheduled closes only.
- Show publication, entry, and local time separately in the Dashboard/API; dim `deactivated` signals with a **DO NOT ENTER** warning, filter legacy slots, and remove the dead RHYTHM/H11 chart paths.

## [v3.17.1] - 2026-07-23

- Write scheduled-close JSON through per-writer temporary files, Windows-lock retries, and shared worker/NativeQt transactions, preventing both `Loop Error [WinError 5]` and concurrent lost updates.
- Retain valid H=11 SW/BT records with all four candles in seven-day history so the Dashboard can render the OHLC SVG.
- Make H=7/H=8 priority symmetric for either H=5 direction and avoid fabricating a badge when the H=6 candle is unavailable.
- Reverse XAUUSD direction at H=15 on Wednesday.
- Temporarily remove the Telegram fast order inline keyboard to prevent conflicts with `/pending` syntax.
- Fully synchronize Thursday H=2 and H=3 rules: Strictly reuse Monday's exact signal data (both XAUUSD and GBPAUD) and its Priority label. Updated Dashboard rule text accordingly.

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
