# Changelog

All notable changes to the dashboard are recorded here.

## Unreleased

### Added

- Fact Check Image Authenticity as a separate media domain: upload → bounded image validation → metadata/provenance observations → Gemini 3.6 Flash multimodal assessment → normalized evidence-calibrated verdict → existing share/public-result loop.
- Dual image intent in `/factcheck`: OCR claim extraction remains available while JPEG/PNG/WEBP images can explicitly run authenticity analysis.
- Shared Fact Check schema `v3` discriminates `claim` and `media_authenticity` results while retaining schema 1/2 claim-share reads.

### Security / privacy

- Direct authenticity uploads are capped at 4 MB to remain below the Vercel Function request-body boundary; dimensions and pixel count are bounded before model invocation.
- Raw uploaded image bytes, GPS and device identifiers are never persisted in Redis/public shares; public records contain only bounded technical facts and the normalized report.
- C2PA/Content Credentials support is marker-presence only (`present_unverified`), not cryptographic verification. Missing provenance or EXIF never implies AI generation, and editor tags are weak observations rather than manipulation proof.

### Changed

- Media model SSoT is `FACTCHECK_MEDIA_MODEL`, defaulting to `gemini-3.6-flash`; text/URL Fact Check keeps its existing model owner.
- Image-authenticity verdicts are evidence-calibrated (`provenance_verified`, `likely_ai_generated`, `likely_manipulated`, `no_material_manipulation_detected`, `inconclusive`); confidence is evidence strength, not an AI-generation probability.

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
