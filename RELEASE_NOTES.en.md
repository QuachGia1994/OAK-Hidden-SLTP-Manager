# RELEASE NOTES

## [Signal logic v87.2] - 2026-08-01

- Document the canonical pipeline as four layers: Layers 2–3 choose the XAUUSD Entry Plan, Layer 1 produces the Reference Signal from GBPUSD D plus the resolved Entry branch/Day Mode (with the H:49 XAU H1 exception), and Layer 4 applies Final Reverse once.
- Fix the v87 MT4 Feed connection for WebRequest: the EA uses `http://127.0.0.1/mt4-feed` on default HTTP port `80`; `:5001` is now local health/management only. One EA auto-detects symbols per supported chart and replaces the legacy `:5000/mt4_data` feeder.
- Keep the manual Copy Trade Close All path and existing Auto Closed Opposite behavior untouched; Signal Bot still does not create a duplicate Auto-Close schedule.

## [Signal logic v87.1] - 2026-08-01

- Remove Auto-Close from the Signal Bot completely; it no longer closes positions and Copy Trade does not create a duplicate close schedule from Signal core.
- Remove special/post-special slot suppression; every H3/H7/H9/H12/H14/H16 slot runs Monday–Friday. Special dates only feed Final Reverse for H3/H14/H16.

## [Signal logic v87] - 2026-08-01

- Connect the raw MT4 EA feed to a persistent SQLite store; MT4 is the market-data and Broker-clock authority, while MT5 remains execution/account/position only.
- Split Data/Execution heartbeat state, catch up due slots after late clock recovery, fail closed on stale feed, and remove MT5 candle fallback from the Signal Engine.
- Compute independent per-symbol D-Direction from the previous-session H4 20:00 candle; use one common XAUUSD Entry Plan for all five pairs and two XAUUSD H1 layers for H16.
- Raise dashboard/evidence to schema 9, filter legacy logic records, show MT4 Feed/MT5 Execution/Broker Clock separately, and keep Auto-Close outside the Signal Bot scope.

## [Signal logic v72.1] - 2026-07-30

- Fix the XAUUSD mapping: start from the final GBPAUD Signal, reverse it at H3/H14/H16, and keep it at H7/H9/H12.
- Let VIP evidence fall back to `pair_evidence` in the signal snapshot when startup rebuild has not seeded the dedicated evidence store; request the card's exact logic version.
- Prefer evidence embedded in the displayed snapshot so a stale key cannot override a new card; preserve GBP entry, weekend free-VIP access, and revision metadata.
- Reuse the API's complete public mask during SSR so entries, groups, and evidence are never serialized for public users.

## [Signal logic v72] - 2026-07-30

- Replace the active engine with the completed-M30 sequence `GBP Signal → XAU Layer 1 → XAU Layer 2`; four GBP pairs independently derive direction, while the two XAUUSD layers select entry only.
- XAUUSD follows GBPAUD direction: H7/H9/H12 are opposite; H3/H14/H16 match. XAU uses the two-layer entry table, and GBP entry is the next full Broker hour after XAU.
- Synchronize Signal Bot, comparator API, MT4 feeder, Dashboard evidence/cards, canonical rules, and docs; missing/DOJI data fails closed and records before logic version 72 are excluded from the active UI.

## [Signal logic v71] - 2026-07-29

- Restore independent Stage-B signals for `XAUUSD`, `GBPUSD`, `GBPAUD`, `GBPJPY`, and `GBPCAD`: H7/H9/H12/H14/H16 use exact H1 C1..C4 windows and the ten-rule SW/BT matrix; entry selects C1 and only `15:25`/`16:49` apply the extra exception reversal.
- H3 uses previous-session H1 04:00 (C1/Base), 03:00, and 02:00 with the three-candle matrix. Thursday uses the same week's Monday source: BT keeps the result, while XAUUSD SW returns WAIT and resumes from H7.
- Synchronize Signal Bot, the MT4 feeder, MT4/MT5 comparator, Dashboard evidence/API, canonical rule contract, documentation, and regression tests; logic version 71 filters stale records.

## [v3.18.2] - 2026-07-29

- GBPAUD takes the direction of the completed H1 bar immediately before the signal slot (H3 uses H2, H7 uses H6, etc.) instead of using M15 Base/pattern/post-filter. TANG → BUY, GIAM → SELL. The M15 offset -15 and H:45 follow-up are only used for XAU entry timing.
- Raise the signal contract to logic version 67.

## [v3.18.2] - 2026-07-28

- Replace the complete signal matrix with one rule for H=3/H=4/H=6/H=9/H=12/H=14/H=16: derive XAUUSD from the two equivalent-slot GBPUSD H1 candles on the previous Broker day, using GBPAUD only as the comparison branch for entry selection.
- Matching derived directions enter at `H:11`. Opposite directions classify today's three XAUUSD M15 candles after skipping the immediately preceding bar; for H=9 this skips 08:45 and uses exactly 08:30/08:15/08:00 to choose `H:49` or `(H+1):25` (03:49/04:25 for H=3).
- Keep fail-closed behavior for missing candles or unresolved DOJI, emit XAUUSD only, retain H=4 as `deactivated`, and remove H=5 together with retired M30/4H1/priority/RHYTHM logic.
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
