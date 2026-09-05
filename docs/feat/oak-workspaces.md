# OAK workspaces
updated 2026-09-05 unreleased

The six-screen concept is a visual reference, not a source of financial data or API behavior.

## Routes and contracts
- /engine: latest retained broker-day H1 matrix. Entry hour and BUY/SELL remain rule-derived.20s refresh is a refresh cadence, not a heartbeat claim. Conditional H16 CLOSE remains advisory.
- /history: same matrix and evidence with an embedded Sunday-first calendar. Available days come from the retained feed, not fabricated calendar coverage.
- /tools: directory for the existing three tool routes. OAK_TOOLS in dashboard/src/lib/oak-tools.ts is shared by the directory and NavBar.
- /factcheck: text/link and image input modes preserve their drafts. OCR returns editable text to the text mode; image authenticity retains independent origin, generation, manipulation and completeness results. APIs and public sharing are unchanged.
- /tarot: existing78-card deck and one/three draws. Decorative card backs do not replace real card artwork or the server draw. Cards-only partial results and errors remain supported.
- /discover: Daily, Oracle and Mood remain local; only Dream and Compatibility use the AI endpoint.

## Presentation owners
- globals.css owns existing OAK semantic color, type, radius and motion tokens. Dark surfaces use the navy concept palette; light and contrast variants remain available.
- oak-redesign.css owns shared workspace styles. Existing H1/Lab declarations are edited at their owner. New patterns are oak-tool-art, oak-tool-card, oak-tool-directory, oak-workspace-heading, oak-input-modes, oak-image-dropzone and oak-access-pill.
- ToolArtwork is a decorative, aria-hidden SVG with a finite kind variant and unique gradient IDs. It follows theme tokens and does not replace the canonical oak-app-icon.png brand.
- SundayCalendarPicker's embedded variant reuses the same date selection and month math; it is a region rather than a dialog and remains in document flow on mobile.
- New tools are reachable through the existing keyboard-operable menu and breadcrumbs. No new account or payment workflow is introduced.

## Verification
Existing306-test dashboard suite and TypeScript pass. All six routes compile and render their expected SSR content with HTTP200 on the Windows Next dev preview.
Desktop/mobile screenshot comparison, browser interactions and production deployment are not yet verified for this revision. Do not claim100% visual parity or AI service health from these checks.
