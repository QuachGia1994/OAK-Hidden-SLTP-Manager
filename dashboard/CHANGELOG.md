# Changelog

All notable changes to the dashboard are recorded here.

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
