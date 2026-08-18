# Changelog

All notable changes to the dashboard are recorded here.

## [0.3.0] - 2026-08-18

### Added

- Shareable Fact Check results with public URLs at `/factcheck/<id>`.
- Persist normalized FactCheckResult in Upstash Redis (`oak:factcheck:share:<id>`, 30-day TTL).
- Dynamic Open Graph / Twitter metadata and branded OG image for social previews.
- Share + Copy Link actions (Web Share API on mobile, clipboard fallback).
- Public result page with evidence-first layout and “Check another claim” CTA.
- Domain helpers: claim normalize, verdict presentation mapping, analytics event boundary.
- Focused Fact Check share unit tests (`npm run test:factcheck`).

### Changed

- Fact Check API returns `shareId` / `sharePath` after successful checks.
- FactCheckResult now carries `claim`, `normalizedClaim`, `checkedAt`, and `locale`.

## [0.2.0] - 2026-08-16

### Added

- Add bilingual one-card and three-card Tarot reflections at `/tarot`.
- Add secure server-side card draws from a complete 78-card deck.
- Add structured Gemini interpretations with safety boundaries and explicit failure states.
- Add Tarot validation, rate limits, focused tests, and responsive card states.

### Changed

- Share the server-side rate-limit utility across Tarot and Fact Check APIs.
- Add Tarot navigation, metadata, environment examples, and operator documentation.

## [0.1.0] - 2026-08-15

### Added

- Initial dashboard release. Historical details were not recorded in a changelog.

