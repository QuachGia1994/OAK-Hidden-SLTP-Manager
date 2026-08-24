# Changelog

All notable changes to the dashboard are recorded here.

## Unreleased

### Added

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
- H1 signal rule v6/state v12 extends the H8+ Pattern 1 (`TGG`/`GTT`) allowTrade logic with a fallback window: first inspect the prior non-overlapping trio (H4/H3/H2 at H8); Pattern 1/2 blocks and Pattern 3 (`GTG`/`TGT`) reverses once. If that trio is outside all three groups, inspect H5/H4/H3 and apply the same classification. Scanner Pattern 2 bypasses both lookbacks, calendar post-signal remains independent, public schema stays 7, and older rule feeds are rejected instead of carrying stale trade state forward.
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
