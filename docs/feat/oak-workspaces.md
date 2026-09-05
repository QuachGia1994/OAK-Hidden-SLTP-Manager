# OAK workspaces
updated 2026-09-05 unreleased

The six-screen concept defines visual hierarchy; live prices, dates, cards and AI results always come from the existing product.

## Routes and contracts
- /engine: latest retained broker-day matrix, single compact board header, FREE ACCESS and 20s refresh. Click a cell to open inline evidence with original base, final source, chronological OHLC chart and expandable bar details. Conditional H16 CLOSE is advisory.
- /history: the same matrix with an embedded Sunday-first bordered calendar. Only retained dates are enabled. Date changes hide evidence from the previous day.
- /tools: three horizontal illustrated banners, backed by the shared OAK_TOOLS catalog.
- /factcheck: text/link and image drafts survive mode switches. OCR returns editable text; image analysis preserves origin, generation, manipulation and completeness. Public sharing and backend handlers are unchanged.
- /tarot: compact question and one/three-card controls above the real78-card deck. Decorative backs never replace the server draw. AI failure still preserves drawn cards.
- /discover: Daily across the top, then Dream/Oracle and Mood/Compatibility. Daily, Oracle and Mood stay local; only Dream/Compatibility call AI.

## Presentation owners
- globals.css owns semantic tokens, including the navy/cyan dark palette and workspace width. Light and contrast remain available.
- oak-redesign.css owns navigation, WorkspaceHeading, ToolArtwork, workspace layout and image-input composition. Replaced367old selectors before adding the canonical rules. factcheck-share.css retains report/share semantics; overlapping image-input declarations were moved to their composition owner.
- WorkspaceHeading provides localized01-06titles and subtitles. NavBar uses the real oak-app-icon.png and OAK GATEKEEPER wordmark. Mobile has four direct tabs; desktop retains a keyboard-operable tools menu. Directory links use flex layout, never the icon/detail grid.
- ToolArtwork's finite kind maps to one generated transparent3x3atlas, dashboard/public/oak-workspace-atlas-v2.webp (489488bytes, SHA256 df9d9969b7e9fe908123ea053ebf7867490461413454dfef870308fb9db7fa73). Built-in ImageGen prompt: premium luminous navy/cyan/violet/gold painterly3D sprite sheet; photo+magnifier, fanned tarot, compass; mountain sunrise, crescent clouds, oracle sphere; crystal hearts, ornate single card back, night clouds. No text, labels or data. WebP is a format conversion of the generated original. This is concept-directed new artwork, not pixel-identical extracted art.
- H1EvidencePanel retains its dialog variant with focus trapping; inline variant is a normal region. Copy chart uses the same renderer.
- /workspace-review.html is a noindex visual QA harness: same-origin real pages at320/393/768/1100px widths. It introduces no mock data or API. This tests responsive layout in Chromium, not iOS Safari engine behavior.

## Verification
-306/306dashboard tests pass; TypeScript passes.
-Source assertions updated for direct mobile navigation, single H1 header and inline evidence; trading/backend assertions retained.
-Browser audit confirmed all6baseline screens differed before the correction. Post-deployment screenshot and interaction evidence is recorded in the shared task plan.
-No literal100%pixel-parity or AI health claim follows from unit tests. Concept has illustrative results and sample signals that must never be fabricated in production.
