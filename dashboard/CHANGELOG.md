# Changelog

All notable changes to the dashboard are recorded here.

## [0.6.1] - 2026-08-26

### Fixed

- `/accounts` now follows the global EN/VN locale across the admin sign-in state, provider descriptions, MT5 registration form, account controls, confirmations, errors and empty states. Added a regression contract for the exact EN admin-login copy shown after a 401 response.

## [0.6.0] - 2026-08-26

### Added

- Added `/neotech` customer Visual Profile with Investor Password as the recommended onboarding path, optional Master Password pairing behind an explicit risk warning/acceptance, compiled + auditable-source MT5 telemetry connector downloads, server-side NeoTech rule evaluation, radar/rule evidence views, coverage/FDD/month tracking, private browser workspaces, one-time pairing, revoke and immediate data purge.
- Copy actions in NeoTech onboarding now show a visible success/error toast so users can confirm that pairing codes and WebRequest URLs actually reached the clipboard.

### Fixed

- NeoTech C9 now evaluates deposit/withdrawal events only from the first trading episode onward. Demo-account opening balance/funding events that occur before the evaluation starts no longer create a false C9 violation; later deposits/withdrawals still fail C9.

### Security / privacy

- Public NeoTech analytics is isolated from MT5/cTrader/Telegram execution surfaces by build-time contract tests. Investor/read-only remains the default; `ACCOUNT_TRADE_ALLOWED=true` is accepted only when the browser-created one-time pairing explicitly records `TRADING_CAPABLE_ACCEPTED`. MT5 passwords are never sent to OAK, connector bearer tokens are retained only as SHA-256 hashes, raw deal/cash-flow bodies are not persisted, retained derived/account/equity/audit data has a 400-day maximum sliding retention, and missing evidence remains fail-closed instead of being inferred PASS.

### Changed

- Telegram `/help` and `/start` now show NeoTech `/check` examples for summary, C5, violations, pagination and group use. `/check @profile 2` now selects summary page 2 directly.
- NeoTech now follows the global EN/VN locale for its public workspace, pairing flow, timestamps, status labels and account actions. Hardcoded NeoTech status/accent colors now reuse the shared OAK semantic tokens across light/dark/contrast themes.

### Fixed

- Telegram `/help` and `/start` now respond even when the chat is not the configured cloud-control chat. The bypass is limited to read-only help; trading/control commands remain chat-fenced.
- Fixed dashboard UI/UX regressions: the EN/VN switch remains available on mobile, provider-account network/API failures no longer masquerade as an admin-auth lock, VIP/H1/NeoTech dialogs trap keyboard focus and close with Escape, VIP logout failures remain visible, expired/missing shared Fact Check pages respect the active locale, NeoTech Copy actions report success/failure, and the removed H1 `PROFILE` card no longer reappears.
- Added a UI/UX contract test to the normal test/build gate so the repaired mobile locale, account error-state, dialog focus, H1 header and locale contracts are regression-checked.

## [0.5.0] - 2026-08-25

### Added

- Added a PC-local MT5 Telegram failover path for verified Upstash write-capacity/outage events. Healthy operation keeps the production webhook in cloud ownership; activation requires fresh matching EA cloud-failure evidence plus repeated independent Redis `SET ... EX` write-canary failures. MT5 mutation intents carry canonical per-line/per-account origins through cloud execution and the bridge into the EA, where cloud/local `entry`, `close`, `modify`, and `partial` share a retained FILE_COMMON per-origin claim/result fence; claim-without-result is fail-closed `UNCERTAIN`, while `positions` remains read-only. Local IDs use `L-<epoch>-<seq>`, recovery fences handled Telegram updates before restoring/verifying the production webhook, and offline verification does not install the Scheduled Task or perform a live handoff/outage simulation.

### Fixed

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
