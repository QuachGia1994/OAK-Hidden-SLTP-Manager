# Changelog

All notable changes to the dashboard are recorded here.

## Unreleased

### Added

- Added an admin-authenticated `/api/mobile/h1` JSON adapter for the native OAK Gatekeeper app. It reuses the normalized H1 feed/cooldown logic, masks future slots, returns no server credentials, and lets Android/iOS share the same Vercel source of truth as `/engine`.
- Media Forensics v3: provider-neutral specialist-detector registry, explicit UniversalFakeDetect class-boundary calibration semantics, bounded C2PA/detector timeout/concurrency policy, deterministic evidence fusion, and an isolated `services/media-forensics/` service path combining official `c2pa-python` verification with UniversalFakeDetect.
- Fact Check Image Authenticity as a separate media domain: upload → bounded image validation → metadata/provenance observations → Gemini 3.6 Flash multimodal assessment → normalized evidence-calibrated verdict → existing share/public-result loop.
- Dual image intent in `/factcheck`: **Check claims in image / Kiểm tra nội dung trong ảnh** remains the OCR→Text path, while **Detect AI Image / Phát hiện ảnh AI** explicitly enters the media-authenticity path.
- Shared Fact Check schema `v3` discriminates `claim` and `media_authenticity` results while retaining schema 1/2 claim-share reads.

### Security / privacy

- Direct authenticity uploads are capped at 4 MB to remain below the Vercel Function request-body boundary; dimensions and pixel count are bounded before model invocation.
- Raw uploaded image bytes, GPS and device identifiers are never persisted in Redis/public shares; public records contain only bounded technical facts and the normalized report.
- C2PA/Content Credentials becomes cryptographically verifiable only through the external forensics service with explicit trust anchors; absent runtime activation, marker presence remains `present_unverified`. Missing provenance or EXIF never implies AI generation, and editor tags are weak observations rather than manipulation proof.
- UniversalFakeDetect raw sigmoid scores remain server-internal and are never rendered as an “AI probability”. Until a controlled OAK calibration set exists, the upstream 0.5 class boundary produces weak directional evidence only; unknown versions/invalid scores become `uncertain`. Material detector/Gemini disagreement lowers the final verdict to `inconclusive` unless any trusted verified C2PA provenance is authoritative.
- The forensics sidecar performs its own full image decode, terminal-container checks and bounded concurrency. It accepts authenticated bytes only and does not log/persist image bodies, raw detector scores or manifests.
- Specialist detector deployment is reproducible with a pinned Python dependency lock and runtime health/version/inference contract, but current production has no remote forensics URL/token or GPU host. Status remains **SPECIALIST DETECTOR READY — REMOTE RUNTIME BLOCKED BY INFRASTRUCTURE** until controlled live inference proves activation.

### Changed

- Image Authenticity client handling now accepts `image/jpg`, `image/pjpeg`, and extension-only JPEG/PNG/WEBP selections while leaving server magic-byte validation authoritative; oversized and unsupported client errors are distinct, selected images render a local preview thumbnail, and Gemini media timeout is 55s within the 60s route budget.
- Image Authenticity wording is evidence-based (`Check image authenticity` / `Xác thực ảnh`) across input, result/public views and OG metadata instead of binary `Detect AI Image`; `likely_manipulated` is now an explicit evidence-agreement direction so detector-vs-visual disagreement becomes `mixed` and downgrades to `inconclusive` without trusted provenance.
- H1 pure cells now show an explicit `⚠ PURE` badge; stale delivered H12-H15 rows are reconciled before the delivered-slot skip so H12 pure + H15 pure is corrected to H15 `BLOCK / NOT TRADE`, while normal SW remains actionable.
- `/accounts` now separates cTrader and MT5 into dedicated tabs; each tab shows only its provider actions/forms/accounts while keeping the same server-side account API contract.
- H1 blocked pure slots now fill the entire matrix cell with a stronger warning background/border, making `BLOCK / NOT TRADE` visually distinct instead of tinting only the inner button/span.
- H1 pure cooldown now blocks only repeated pure SW3 matches inside the next three slots; normal SW3 signals remain actionable, and the web marks only an actually blocked pure slot as `BLOCK / NOT TRADE`.
- Media model SSoT is `FACTCHECK_MEDIA_MODEL`, defaulting to `gemini-3.6-flash`; text/URL Fact Check keeps its existing model owner.
- Image-authenticity verdicts are evidence-calibrated (`provenance_verified`, `likely_ai_generated`, `likely_manipulated`, `no_material_manipulation_detected`, `inconclusive`); confidence is evidence strength, not an AI-generation probability. Visual-only/weak-only AI conclusions now downgrade to `inconclusive` without trusted provenance or live specialist support.
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
