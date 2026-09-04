# Changelog

All notable changes to the dashboard are recorded here.

## [Unreleased]

### Added

- Added click-through H1 pattern evidence for populated Live/History cells. The evidence panel uses the exact retained local ICMarkets M15 OHLC bars used by matching, shows source symbol, block/entry, SW/BT, original GT/TG or TT/GG family, final pattern and weekday inversion, supports copyable evidence text, and renders a dependency-free SVG candlestick chart with sampled-window, BLOCK and ENTRY markers. Mobile presents the same evidence as a bottom sheet.

- Added the PC-local scheduled MT5 entry driver and EA v1.08 preparation contract. Only due `entry` intents may use targeted MT5 order-window messages with no global mouse/keyboard injection; immediate entry and every management action remain on the EA mailbox path, while ambiguous submit outcomes are durably `UNCERTAIN` and never replayed automatically.

- Added idempotent Telegram entry scheduling support for live H1 operations. Existing pending H1 intents are backfilled for notification when their entry time is near, fixed lots are 0.05 for FX and 0.01 for XAUUSD on the $5,000 sizing policy, and pending H1 intent lots are normalized before approval. H1 history now uses a visual native calendar picker with weekday filters and broker-date bounds. Scanner-originated block/signal Telegram reminders were subsequently retired in favor of operator-entered timed commands feeding the web table.

- Reworked the H1 core as state v54 / public feed schema 16 / signal rule 49. Entry signals use the broker H1 candle one hour before entry (`08:00` and `08:25` both read `H07:00`) as the base direction for all FX and XAUUSD; M5 Bollinger is no longer authoritative. The six-block weekday inversion/keep matrix is applied uniformly across symbols and weeks, with cycle-month Thu/Fri, Tue/Wed and Monday groups matching the published rule, and non-cycle Thursday months using the inverse matrix. Fixed lots remain `0.05` FX / `0.01` XAUUSD; the `/approve ID` broker-mutation boundary is unchanged.

- Added revocable NeoTech profile share links. Owners can create 30-day read-only links, copy the secret URL once, list active links, revoke one or revoke all, while shared viewers receive live server-authoritative profile updates without workspace access, MT5 credentials, connector tokens, raw trades, ticket IDs or cash amounts. Share secrets stay in the URL fragment and are resolved through a bearer header; the server stores only SHA-256 hashes.

### Fixed

- Fixed H1 Evidence chronology and source clarity. M15 charts render oldest → newest left-to-right across Web/native iOS/native Android and copied/shared chart PNGs, while Pattern Bars retain scanner order newest → oldest. Key Facts now uses BASE CANDLE for the raw previous-broker-day H1 input and only shows FINAL SOURCE for non-direct rules, so DIRECT BASE cells no longer duplicate the same source twice.
- Corrected H1 Evidence Key Facts across Web/native iOS/native Android. Pattern scanner source is now distinct from RAW BASE and actual SIGNAL SOURCE; H16 explicitly shows same-symbol H14 + COPY/INVERT rule, GBPUSD/EURUSD sync blocks show XAUUSD as the signal source, direct blocks identify the previous-broker-day raw base, and FINAL is always shown separately. Removed iOS's hardcoded GBPUSD BASE label and kept CLOSE additive to BUY/SELL.
- Fixed native H1 schedule PNG export parity with Live: iOS uses a dedicated non-scroll export matrix sourced from the same `h1.hours` and `h1.alert(date:symbol:hour:)` data as the on-screen matrix, preventing ImageRenderer from dropping the scrollable block columns. Android's direct Canvas exporter is contract-tested against the same data source.
- Fixed native mobile PNG/chart handoff to other apps. Android no longer deletes fresh FileProvider exports when OAK goes `UI_HIDDEN`, keeps PNG cache URIs valid long enough for Telegram paste, and provides explicit `SHARE PNG` / `SHARE CHART` ACTION_SEND fallbacks. iOS now copies explicit PNG UTType bytes instead of UIImage-only pasteboard state and provides UIActivityViewController share fallbacks backed by retained cache files.
- Advanced local H1 to v74. H16 keeps its existing entry hour/pattern evidence but derives final BUY/SELL from that symbol's H14 signal: XAUUSD H3 entry H5 copies H14 with no CLOSE badge; XAUUSD H3 entry H4 inverts H14 and enables the CLOSE advisory badge. Web/PNG/native iOS/native Android use the same H4-only CLOSE predicate.
- Fixed missing selectable dates in H1 History: valid ICMarkets broker days are retained even with zero pattern matches, and local historical publishing retries transient singleton-lock `already-running` responses instead of silently skipping that date during overlap with the minute live scanner.
- Advanced local H1 to v73. H16 keeps normal entry-time calculation and BUY/SELL rendering on XAU H5 manual-close days; CLOSE remains an advisory badge only and no longer suppresses or replaces the H16 signal on Web, native iOS/Android or copied H1 PNGs. H1 persistence now uses schema-stable `state:s56`; first load merges retained v72/v73 state, repairs legacy CLOSE-only H16 rows, and keeps the 90-day History calendar intact across future rule-only bumps.
- Advanced local H1 to v72. GBPUSD and EURUSD H9/H12/H14/H16 now take the same entry time as XAUUSD for each block while retaining v71 signal synchronization and eligibility. Removed XAUUSD/GBPUSD reference-cell tinting from web/native matrices and H1 PNG exports, while preserving H16 CLOSE warning styling. A fresh v72 state key prevents stale entry times.
- Advanced local H1 to v71 and hardened local scheduled reversals. Tuesday GBPAUD now keeps its AUDUSD-derived side, Thursday GBPUSD follows XAUUSD without inversion, and Friday EURUSD follows XAUUSD without inversion; all v70 block eligibility remains unchanged and a fresh v71 key removes stale flipped rows. EA v1.11 moves exposure validation after opposite-side net settlement and the PC scheduler converts unexpected due-intent exceptions into durable Telegram-visible failed/uncertain outcomes instead of silently dropping the run.
- Advanced local H1 rule to v70. GBPAUD remains active on all six H3/H6/H9/H12/H14/H16 blocks Tuesday-Friday; GBPJPY no longer calculates H3 and starts at H6; GBPCAD no longer calculates H3/H6 and now shares the GBPUSD/EURUSD H9/H12/H14/H16 eligibility. Monday remains XAUUSD-only, while shared GBPUSD entry timing and AUDUSD/USDCAD/USDJPY signal bases remain unchanged. The fresh v70 key clears stale early-block rows.
- Advanced local H1 rule to v69. Monday is XAUUSD-only again: GBPAUD, GBPCAD and GBPJPY are blank for all H3/H6/H9/H12/H14/H16 Monday blocks, while their v68 GBPUSD-shared entry timing and AUDUSD/USDCAD/USDJPY signal-base rules continue Tuesday-Friday. The v69 state key clears stale Monday cross rows.
- Advanced local H1 rule to v68. GBPAUD, GBPCAD and GBPJPY are visible again and all three use GBPUSD M15 pattern/evidence for one shared entry-time schedule across H3/H6/H9/H12/H14/H16. Their final BUY/SELL bases are now independent previous-broker-day candles at H(entry-1): AUDUSD for GBPAUD, USDCAD for GBPCAD and USDJPY for GBPJPY. The ICMarkets reader/publisher now includes USDCAD and preserves previous-day bars for all four base sources; old GBP-cross H3/H6 inversion behavior is removed. H16 CLOSE-only remains authoritative on an XAUUSD-start-H5 day.
- Increased H1 light-theme matrix contrast after mobile Safari review: blue entry-reference cells and amber CLOSE cells now have stronger fills/inset borders, while BUY/SELL/CLOSE pills use thicker light-theme outlines. Dark theme is unchanged.
- Advanced local H1 rule to v67. XAUUSD first-day entry H5 no longer flips H16 signals. Instead H16 becomes a manual `CLOSE` advisory: H16 BUY/SELL output is null for every row while entry/pattern evidence stays available, and web/mobile/PNG render a `CLOSE` badge. There is no automatic broker close wiring; only the user may choose to close positions.
- Temporarily hid GBPCAD and GBPJPY from H1 web Live/History, PNG export, and mobile Calendar/Signals presentation while keeping backend calculations and feed data intact for easy restoration.
- Advanced local H1 signal rule to v66. EURUSD H9/H12/H14/H16 inherits GBPUSD entry timing. GBPCAD and GBPJPY both inherit GBPAUD entry time + final signal at H3/H6; at H9/H12 they inherit GBPUSD entry time + XAUUSD final signal; at H14/H16 they retain GBPUSD entry time/evidence but publish a blank signal. GBPCAD keeps GBPJPY/USDJPY pattern/evidence derivation at H9+. GBPAUD H3/H6 and GBPUSD H9/H12/H14/H16 are highlighted as entry-reference cells. Monday FX-off and the existing 20-second soft refresh remain unchanged.
- Advanced local H1 signal rule to v65. GBPUSD H9/H12/H14/H16 again derives its entry hour from its own GBPUSD M15 pattern, while final BUY/SELL remains synchronized to XAUUSD with the existing Thursday inversion. EURUSD remains synchronized to XAUUSD entry timing/final side and keeps its Friday inversion. GBPCAD timing and the global 20-second soft refresh remain unchanged.
- Advanced local H1 signal rule to v64. GBPUSD/EURUSD H9/H12/H14/H16 now use the XAUUSD pattern driver for the exact same entry hour and final side, while keeping the existing Thursday GBPUSD and Friday EURUSD flips. GBPCAD entry timing is explicitly anchored to GBPAUD at H3/H6 and GBPJPY at H9/H12/H14/H16. Monday stays XAUUSD-only. Restored a global 20-second soft tab refresh via `router.refresh()` so server data updates without a hard browser reload or resetting client selection state.
- Advanced local H1 signal rule to v63. EURUSD is now a sixth row from H9/H12/H14/H16 with its own local ICMarkets pattern-derived entry time. GBPUSD and EURUSD H9+ use the same final side as XAUUSD for that block, except Thursday flips GBPUSD once and Friday flips EURUSD once. Monday remains XAUUSD-only, and the existing XAU-entry-H5 H16 toggle is inherited by the synced rows.
- Advanced local H1 signal rule to v62. If XAUUSD's first entry-time of the broker day is H5, the complete H16 column flips the already-derived final BUY/SELL once more. Per-symbol rules still apply first, so GBPUSD H16 double-inverts back to its GBPUSD base while XAUUSD/GBPAUD/GBPCAD/GBPJPY H16 flip opposite. The old Thursday/Friday propagation and CẦU logic remain disabled/hidden.
- Temporarily changed H1 access to `FREE ACCESS` for every Live/History entry cell, including XAUUSD, and removed the H1 VIP unlock/redaction path from those pages. The local H1/Telegram Windows tasks now launch through a hidden `wscript.exe` wrapper so scheduled background work no longer opens console windows while retaining the current user/network context.
- H1 Live timed entries now map the Vietnam appointment schedule explicitly: `09:05→H03`, `10:05→H04`, `12:05→H06`, `15:05→H09`, `18:05→H12`, `20:05→H14`, `22:05→H16`. This prevents IC Markets DST conversion from putting `XAUUSD 10:05` in H06; a safe re-sync clears only the matching legacy side and restores it to H04 without broker execution.
- PC-local scheduled manual entry now changes Volume through MT5's native spinner instead of trusting a visually replaced edit value. This fixes the confirmed FXCE XAUUSD case where requested `0.01` displayed correctly but the terminal submitted its prior internal `0.03`; preparation verifies both `0.01` and `1 XAU`, persists before/after audit evidence, fails closed on mismatch, and never captures the global mouse or keyboard.
- PC-local timed `/close` and `/closeall` commands without `@ACCOUNT` now fan out to every enabled MT5 account; explicit `@ACCOUNT` remains single-target. Natural `Đóng all lúc HHhMM` and `Đóng SYMBOL lúc HHhMM` forms are accepted too. Each account keeps its own durable origin/ledger, and the EA matches base FX/metal symbols against broker prefix/suffix variants before closing positions.
- Telegram BUY/SELL parser now accepts bare `FXCE`/`FxCe` like `Vantage`, and scheduled entries accept both `TIME SL TP` and legacy `SL TP TIME` layouts. This fixes commands such as `Sell XAUUSD 0.01 18h05 FXCE`, with omitted SL/TP still using the selected account defaults.
- Temporarily disabled active H1 post-signal inversion and CẦU/BRIDGE output. Signal rule v58 keeps all live/history H1 directions equal to their base BUY/SELL, suppresses bridge badges/highlights/derived summaries, and leaves the configured N/C matrix plus bridge-calendar helpers in place for fast re-enable.
- Restored all Monday/Tuesday/Wednesday H1 blocks that were previously `X/remove`, so every weekday now uses the complete six-block N/C matrix. Signal rule advanced to v57 and the deploy history rebuild restores missing retained H slots without changing Telegram-scheduled BUY/SELL cells.
- Replaced H1 FX targets `AUDUSD`, `USDCAD`, `USDJPY` with `GBPAUD`, `GBPCAD`, `GBPJPY` across scanner, history feed, timed Telegram table writes and UI rows. Legacy retained rows are ignored during state migration so current XAUUSD/GBPUSD data survives until the GBP-cross history is rebuilt.
- The H1 scanner no longer sends `BLOCK ĐÃ ĐẾN` or H1 signal Telegram notifications. Future manual timed `BUY`/`SELL` entries publish their side immediately into the matching H1 cell using the fixed Vietnam appointment schedule. Scanner/backfill refreshes preserve the manual `scheduledSignal`.
- Redis failover now has one shared authority across Vercel serverless invocations. Once a failoverable primary Redis error promotes backup, later webhook/tick invocations keep reading and writing that backup, primary-to-backup sync is blocked until recovery instead of overwriting newer failover state, and scheduled intents more than two minutes late expire instead of executing stale trades.
- Manual Telegram timed entry/close commands now auto-arm future `HH:MM` / `HHhMM` intents as `scheduled` and run through the existing due tick without `/approve`. Immediate commands, stale/past explicit times and H1 Scanner intents keep the approval boundary, and already-saved `approval_required` intents are not converted into late trades.
- Preserved valid H1 Pattern 2 alerts when entry-relative M15 evidence is flat; once a pattern supplies its entry time, only the prior H1 base-candle lookup gates publication. The H1 table now sizes itself from the active seven hour columns instead of stretching across the legacy 79rem grid.
- Decoupled H1 signal/history persistence from trading-automation readiness. The public table now advances even when the exact cTrader scanner account or Telegram control is unavailable, while intent creation and Telegram delivery remain fail-closed and the route reports the skipped reason.
- Fixed cTrader M15 normalization to key candles by broker date, hour and minute. This prevents cross-hour `:00/:15/:30/:45` collisions that reduced every historical day to four M15 candles and left the H1 table empty; deployment backfill now reconstructs BUY/SELL from the complete provider history.
- Fixed missing broker-day rollover when the Durable Object alarm is absent. Every minute Cloudflare trigger now preserves the Telegram tick and concurrently runs the H1 watchdog, allowing H3 to self-heal independently of delayed GitHub cron delivery.
- Restored observable BUY/SELL output in the H1 table and synchronized its evidence labels with the post-block M15 base/action contract. NeoTech Master Password pairing now uses a keyboard-accessible in-page risk dialog with explicit accept/cancel actions, avoiding browser-native confirmation no-ops while preserving the server-side `TRADING_CAPABLE_ACCEPTED` requirement.


## [0.7.1] - 2026-08-27

### Fixed

- Advanced local H1 to v72. GBPUSD and EURUSD H9/H12/H14/H16 now take the same entry time as XAUUSD for each block while retaining v71 signal synchronization and eligibility. Removed XAUUSD/GBPUSD reference-cell tinting from web/native matrices and H1 PNG exports, while preserving H16 CLOSE warning styling. A fresh v72 state key prevents stale entry times.
- NeoTech Connector v1.0.4 now treats server-confirmed `connector unauthorized` / `account unauthorized` as revoked or purged credentials instead of retrying HTTP 401 forever. It clears only matching stale per-account credential files, stops sync in `WAITING_PAIR`, preserves revocation semantics, and prints the server error for other failures. Generate a fresh pairing code once for a revoked account; no EA detach/attach is required.

## [0.7.0] - 2026-08-26

### Added

- MT5 account switching no longer requires reattaching the OAK EAs. Cloud Manager v1.04 auto-binds the current login/server to the registered provider account and bridge profile with fail-closed unbound behavior, while NeoTech Connector v1.0.3 reloads server-scoped per-account credentials and stays attached in waiting state for accounts that still need pairing/authorization. `/accounts` now stores optional MT5 server identity and exposes an authenticated auto-bind reconciliation action for existing live bridge registrations.

### Fixed

- Advanced local H1 to v72. GBPUSD and EURUSD H9/H12/H14/H16 now take the same entry time as XAUUSD for each block while retaining v71 signal synchronization and eligibility. Removed XAUUSD/GBPUSD reference-cell tinting from web/native matrices and H1 PNG exports, while preserving H16 CLOSE warning styling. A fresh v72 state key prevents stale entry times.
- NeoTech connector v1.0.2 now uses a fresh Master pairing code to replace legacy stored `READ_ONLY` credentials when the terminal is trading-capable, and stores the consumed pairing-code hash so subsequent restarts reuse the retained connector credential instead of re-submitting a one-time code.
- NeoTech clipboard toasts now render through `document.body` with a higher overlay layer and footer clearance, preventing the page/footer stacking context from covering Copy feedback.

## [0.6.1] - 2026-08-26

### Fixed

- Advanced local H1 to v72. GBPUSD and EURUSD H9/H12/H14/H16 now take the same entry time as XAUUSD for each block while retaining v71 signal synchronization and eligibility. Removed XAUUSD/GBPUSD reference-cell tinting from web/native matrices and H1 PNG exports, while preserving H16 CLOSE warning styling. A fresh v72 state key prevents stale entry times.
- `/accounts` now follows the global EN/VN locale across the admin sign-in state, provider descriptions, MT5 registration form, account controls, confirmations, errors and empty states. Added a regression contract for the exact EN admin-login copy shown after a 401 response.

## [0.6.0] - 2026-08-26

### Added

- Added `/neotech` customer Visual Profile with Investor Password as the recommended onboarding path, optional Master Password pairing behind an explicit risk warning/acceptance, compiled + auditable-source MT5 telemetry connector downloads, server-side NeoTech rule evaluation, radar/rule evidence views, coverage/FDD/month tracking, private browser workspaces, one-time pairing, revoke and immediate data purge.
- Copy actions in NeoTech onboarding now show a visible success/error toast so users can confirm that pairing codes and WebRequest URLs actually reached the clipboard.

### Fixed

- Advanced local H1 to v72. GBPUSD and EURUSD H9/H12/H14/H16 now take the same entry time as XAUUSD for each block while retaining v71 signal synchronization and eligibility. Removed XAUUSD/GBPUSD reference-cell tinting from web/native matrices and H1 PNG exports, while preserving H16 CLOSE warning styling. A fresh v72 state key prevents stale entry times.
- NeoTech C9 now evaluates deposit/withdrawal events only from the first trading episode onward. Demo-account opening balance/funding events that occur before the evaluation starts no longer create a false C9 violation; later deposits/withdrawals still fail C9.

### Security / privacy

- Public NeoTech analytics is isolated from MT5/cTrader/Telegram execution surfaces by build-time contract tests. Investor/read-only remains the default; `ACCOUNT_TRADE_ALLOWED=true` is accepted only when the browser-created one-time pairing explicitly records `TRADING_CAPABLE_ACCEPTED`. MT5 passwords are never sent to OAK, connector bearer tokens are retained only as SHA-256 hashes, raw deal/cash-flow bodies are not persisted, retained derived/account/equity/audit data has a 400-day maximum sliding retention, and missing evidence remains fail-closed instead of being inferred PASS.

### Changed

- Telegram `/help` and `/start` now show NeoTech `/check` examples for summary, C5, violations, pagination and group use. `/check @profile 2` now selects summary page 2 directly.
- NeoTech now follows the global EN/VN locale for its public workspace, pairing flow, timestamps, status labels and account actions. Hardcoded NeoTech status/accent colors now reuse the shared OAK semantic tokens across light/dark/contrast themes.

### Fixed

- Advanced local H1 to v72. GBPUSD and EURUSD H9/H12/H14/H16 now take the same entry time as XAUUSD for each block while retaining v71 signal synchronization and eligibility. Removed XAUUSD/GBPUSD reference-cell tinting from web/native matrices and H1 PNG exports, while preserving H16 CLOSE warning styling. A fresh v72 state key prevents stale entry times.
- Telegram `/help` and `/start` now respond even when the chat is not the configured cloud-control chat. The bypass is limited to read-only help; trading/control commands remain chat-fenced.
- Fixed dashboard UI/UX regressions: the EN/VN switch remains available on mobile, provider-account network/API failures no longer masquerade as an admin-auth lock, VIP/H1/NeoTech dialogs trap keyboard focus and close with Escape, VIP logout failures remain visible, expired/missing shared Fact Check pages respect the active locale, NeoTech Copy actions report success/failure, and the removed H1 `PROFILE` card no longer reappears.
- Added a UI/UX contract test to the normal test/build gate so the repaired mobile locale, account error-state, dialog focus, H1 header and locale contracts are regression-checked.

## [0.5.0] - 2026-08-25

### Added

- Added a PC-local MT5 Telegram failover path for verified Upstash write-capacity/outage events. Healthy operation keeps the production webhook in cloud ownership; activation requires fresh matching EA cloud-failure evidence plus repeated independent Redis `SET ... EX` write-canary failures. MT5 mutation intents carry canonical per-line/per-account origins through cloud execution and the bridge into the EA, where cloud/local `entry`, `close`, `modify`, and `partial` share a retained FILE_COMMON per-origin claim/result fence; claim-without-result is fail-closed `UNCERTAIN`, while `positions` remains read-only. Local IDs use `L-<epoch>-<seq>`, recovery fences handled Telegram updates before restoring/verifying the production webhook, and offline verification does not install the Scheduled Task or perform a live handoff/outage simulation.

### Fixed

- Advanced local H1 to v72. GBPUSD and EURUSD H9/H12/H14/H16 now take the same entry time as XAUUSD for each block while retaining v71 signal synchronization and eligibility. Removed XAUUSD/GBPUSD reference-cell tinting from web/native matrices and H1 PNG exports, while preserving H16 CLOSE warning styling. A fresh v72 state key prevents stale entry times.
- Scheduled MT5 Telegram intents now persist bridge task envelopes as schema v2 with canonical origin, ledger, digest and broker identity. Legacy/stale v1 tasks fail closed before broker execution and are never replayed automatically, preventing the intent #16 task-version rejection from recurring for future intents.

## [0.4.0] - 2026-08-24

### Added

- Added NeoTech compliance report ingestion and Telegram `/check @profile` rendering. The backend authenticates scoped uploads, validates schema/account binding and canonical raw-body hashes, stores immutable reports with bounded audit metadata, and renders stored MQL5 conclusions without reimplementing NeoTech formulas in TypeScript.
- MT5 EA v1.02 now waits for symbol synchronization and a positive bid/ask tick for up to 2.5 seconds before cloud market entry. This removes the observed `tick unavailable` race when a symbol has just been selected into Market Watch while preserving the existing one-shot broker mutation boundary.
- Redis command-efficiency pass for the cloud runtime: MT5 bridge wait timing now matches EA v1.01's bounded 10–15 second cloud poll, Telegram minute tick reads pending intents once and suppresses idle audit writes, audit trimming and owned-lock release use atomic Lua single-command helpers, H1 dual-feed publish uses `MSET`, and cTrader manager avoids unchanged per-position state writes while refreshing persisted state every 12 hours.
- Telegram Cloud accepts up to 10 commands in one message, one non-empty line per command, and tracks intent idempotency per line within the same Telegram update. Batch `/approve ID [ID ...]` and `/del ID [ID ...]` are supported while preserving single-ID behavior and `/del all`.
- Added an admin/API-authenticated `/api/h1-scanner/backfill` endpoint that reconstructs the fixed 90-calendar-day cTrader H1 window with the current signal rule, shares the live scanner lock, skips the current broker day, reports provider coverage and never sends Telegram messages or broker mutations.
- Added broker-date history controls to `/engine`: localized All/Mon-Fri weekday filters, newest-first broker-date chips, retained-window coverage and deterministic selected-date fallback while reusing the existing H03-H17 matrix/detail view.
- Added an admin-authenticated `/api/mobile/h1` JSON adapter for the native OAK Gatekeeper app. It reuses the normalized H1 feed/allowTrade logic, masks future slots, returns no server credentials, and lets Android/iOS share the same Vercel source of truth as `/engine`.
- Media Forensics v3: provider-neutral specialist-detector registry, explicit UniversalFakeDetect class-boundary calibration semantics, bounded C2PA/detector timeout/concurrency policy, deterministic evidence fusion, and an isolated `services/media-forensics/` service path combining official `c2pa-python` verification with UniversalFakeDetect.
- Fact Check Image Authenticity V4 as a separate media domain: upload → bounded image validation → independent Gemini and optional forensics branches → orthogonal origin / AI-generation / editing-compositing / completeness assessments → shared live/public evidence report.
- Dual image intent in `/factcheck`: **Check claims in image / Kiểm tra nội dung trong ảnh** remains the OCR→Text path, while **Check image authenticity / Xác thực ảnh** explicitly enters the media-authenticity path.
- Shared Fact Check schema `v4` writes normalized orthogonal media results while retaining schema 1/2/3 claim-share reads and conservatively adapting schema v3 media-authenticity records at the read boundary.

### Security / privacy

- Direct authenticity uploads are capped at 4 MB to remain below the Vercel Function request-body boundary; dimensions and pixel count are bounded before model invocation.
- Raw uploaded image bytes, GPS and device identifiers are never persisted in Redis/public shares; public records contain only bounded technical facts and the normalized report.
- C2PA/Content Credentials becomes cryptographically verifiable only through the external forensics service with explicit trust anchors; absent runtime activation, marker presence remains `present_unverified`. Missing provenance or EXIF never implies AI generation, and editor tags are weak observations rather than manipulation proof.
- UniversalFakeDetect raw sigmoid scores remain server-internal and are never rendered as an “AI probability”. Until a controlled OAK calibration set exists, the upstream 0.5 class boundary produces weak directional generation evidence only; unknown versions/invalid scores become `uncertain`, and `real_signal` never verifies real-world origin.
- The forensics sidecar performs its own full image decode, terminal-container checks and bounded concurrency. It accepts authenticated bytes only and does not log/persist image bodies, raw detector scores or manifests.
- Specialist detector deployment is reproducible with a pinned Python dependency lock and runtime health/version/inference contract. The sidecar is optional: unavailable/failed forensics is exposed as partial analysis rather than fabricated evidence or a hard dashboard dependency, and specialist classifications only inform the AI-generation axis.

### Changed

- Telegram cloud schedules now accept single-digit `H:MM` / `HhMM` hours without producing an invalid due time; omitted seconds default to `00`.
- H1 cloud state retention now uses one 90-calendar-day SSoT cutoff relative to the newest valid broker-date key instead of counting stored trading-day keys. Historical cTrader reads are DST-aware, sequentially throttled and bounded/paginated; public schema 7, VIP all-date redaction and mobile latest-day behavior remain compatible across rule updates.
- Image Authenticity client handling accepts `image/jpg`, `image/pjpeg`, and extension-only JPEG/PNG/WEBP selections while leaving server magic-byte validation authoritative; oversized and unsupported client errors are distinct, selected images render a local preview with change/remove controls, and upload disclosure/loading status remain explicit. Gemini visual analysis and the optional forensics sidecar run concurrently with bounded provider timeouts inside the 60s route budget.
- Media analysis now uses four orthogonal normalized assessments: origin (`verified_algorithmic` / `verified_capture` / `verified_other` / unverified states), AI-generation evidence, editing/compositing evidence, and analysis completeness. `likely_ai_generated + likely_manipulated` and `verified_capture + likely_manipulated` are compatible facts; `no_material_edit_detected` remains a valid editing observation without proving non-AI or real origin.
- Gemini and forensics return explicit branch Result/status values. One branch failure preserves material evidence from the other; Gemini failure plus trusted C2PA can return a useful partial result; sidecar outage is an expected degraded state; and no branch with material evidence returns retryable `MEDIA_ANALYSIS_UNAVAILABLE` before any share record is created.
- Live and public media results now render one shared localized evidence report with derived headline/badge text, three assessment cards, completeness/unavailable-source status, limitations/next action, and collapsed advanced details. Raw enum labels are not rendered; media shared pages are `noindex,nofollow` while claim-share indexing is unchanged.
- H1 pure cells show an explicit `⚠ PURE` badge; `BLOCK / NOT TRADE` now reflects the current allowTrade decision while normal scanner Pattern 2 remains actionable.
- `/accounts` now separates cTrader and MT5 into dedicated tabs; each tab shows only its provider actions/forms/accounts while keeping the same server-side account API contract.
- H1 blocked pure slots now fill the entire matrix cell with a stronger warning background/border, making `BLOCK / NOT TRADE` visually distinct instead of tinting only the inner button/span.
- H1 signal rule v12/state v18 makes broker H4 XAUUSD-only and remaps USDJPY to scanner USDJPY + base XAUUSD reversed. FX targets return no matches when evaluated at broker H4, while historical FX rows remain H3/H06-H16. EURUSD, AUDUSD and USDCAD continue to use scanner GBPUSD and reverse their own H1 base; XAUUSD continues to use scanner XAUUSD with GBPUSD base unchanged. H5 remains excluded, FX H6 and XAUUSD H6/H7 pair gates, H8+ allowTrade, DST and Thursday/Friday post-signal ordering are unchanged. Public schema stays 7 and older signal-rule feeds are rejected under rule v12.
- Media model SSoT is `FACTCHECK_MEDIA_MODEL`, defaulting to `gemini-3.7-flash`; text/URL Fact Check keeps its existing model owner.
- Image-authenticity V4 uses categorical `weak | moderate | strong` evidence strength per assessment; the old single numeric media confidence survives only inside the schema-v3 compatibility adapter and is not authoritative V4 state.
- Media request daily rate limits are now isolated per client instead of sharing one global daily bucket across the whole site; the per-minute client isolation remains unchanged.
- UniversalFakeDetect is now live on the Windows i9-9900K CPU sidecar behind Cloudflare Tunnel; production introspection only reports `active` after `/health` and `/version` succeed.

## [0.3.1] - 2026-08-18

### Added

- Fact Check URL input: pure http(s) paste triggers server-side safe fetch + article extraction.
- SSRF guards (localhost, private IPv4/IPv6, metadata, credentialed URLs, redirect validation).
- Article extraction from HTML (`article`/`main`/OG/JSON-ish meta) with bounded payload.
- Semantic URL error codes and EN/VN messages.
- Source-article panel on results and public share pages (snapshot only; no re-fetch).

### Changed

- Canonical pipeline: Text | Image OCR | URL → same Gemini + evidence path.
- Evidence search excludes subject article URL and uses title-bounded queries for long articles.
- Shared schema version bumped to 2 (optional `sourceDocument`); schema 1 shares still readable.
- DNS-pinned URL fetch now supports Node/Vercel `lookup({ all: true })` callback shape, fixing production-wide `URL_FETCH_FAILED` without weakening SSRF pinning.

### Security

- No client-side arbitrary URL fetch; no credential forwarding; max redirects/body/timeout enforced.

## [0.3.0] - 2026-08-18

### Added

- Shareable Fact Check results with public URLs at `/factcheck/<id>`.
- Persist normalized FactCheckResult in Upstash Redis (`oak:factcheck:share:<id>`, 30-day TTL).
- Dynamic Open Graph / Twitter metadata and branded OG image for social previews.
- Share + Copy Link actions (Web Share API on mobile, clipboard fallback).

## [0.2.0] - 2026-08-16

### Added

- Tarot reflections, deck draws, Gemini interpretations, rate limits.

## [0.1.0] - 2026-08-15

### Added

- Initial dashboard release.
