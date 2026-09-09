import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const navSource = readFileSync(new URL("../components/NavBar.tsx", import.meta.url), "utf8");
const h1EngineSource = readFileSync(new URL("../components/H1EngineBoard.tsx", import.meta.url), "utf8");
const h1SignalSource = readFileSync(new URL("../components/H1SignalBoard.tsx", import.meta.url), "utf8");
const h1EvidenceSource = readFileSync(new URL("../components/H1EvidencePanel.tsx", import.meta.url), "utf8");
const enginePageSource = readFileSync(new URL("../app/engine/page.tsx", import.meta.url), "utf8");
const accountSource = readFileSync(new URL("../components/ProviderAccountsPanel.tsx", import.meta.url), "utf8");
const dialogHookSource = readFileSync(new URL("../hooks/useDialogFocusTrap.ts", import.meta.url), "utf8");
const neoTechSource = readFileSync(new URL("../app/neotech/NeoTechPublicDashboard.tsx", import.meta.url), "utf8");
const factCheckSharedSource = readFileSync(new URL("../app/factcheck/[id]/page.tsx", import.meta.url), "utf8");
const factCheckPublicSource = readFileSync(new URL("../components/factcheck/FactCheckPublicView.tsx", import.meta.url), "utf8");
const factCheckWorkspaceCss = readFileSync(new URL("../components/factcheck/factcheck-workspace.module.css", import.meta.url), "utf8");
const factCheckShareCss = readFileSync(new URL("../app/factcheck-share.css", import.meta.url), "utf8");
const oakCss = readFileSync(new URL("../app/oak-redesign.css", import.meta.url), "utf8");
const neotechCss = readFileSync(new URL("../app/neotech/neotech.module.css", import.meta.url), "utf8");
const globalsCss = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
const layoutSource = readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8");
const spatialSource = readFileSync(new URL("../components/SpatialHudCanvas.tsx", import.meta.url), "utf8");
const breadcrumbSource = readFileSync(new URL("../components/RouteBreadcrumbs.tsx", import.meta.url), "utf8");
const historyPageSource = readFileSync(new URL("../app/history/page.tsx", import.meta.url), "utf8");
const toolsPageSource = readFileSync(new URL("../app/tools/page.tsx", import.meta.url), "utf8");
const toolsClientSource = readFileSync(new URL("../app/tools/ToolsClient.tsx", import.meta.url), "utf8");
const tarotSource = readFileSync(new URL("../components/tarot/TarotExperience.tsx", import.meta.url), "utf8");

test("mobile keeps locale reachable and exposes three direct navigation tabs", () => {
  assert.ok(navSource.includes("oak-locale-switch"));
  assert.ok(navSource.includes("setLocaleMode(item)"));
  assert.ok(navSource.includes("router.refresh()"));
  assert.ok(!navSource.includes("window.location.reload"));
  assert.ok(navSource.includes('href="/tools" className="oak-nav-link oak-tools-mobile-link"'));
  assert.doesNotMatch(navSource, /mobileOpen|oak-mobile-nav-toggle|data-mobile-open/);
  assert.ok(oakCss.includes(".oak-tools-mobile-link { display: inline-flex; }"));
  assert.ok(oakCss.includes("grid-template-columns: repeat(3,minmax(0,1fr))"));
  assert.ok(oakCss.includes(".oak-tools-menu > .oak-tools-directory-link { display: flex;"));
});

test("provider account load failures do not masquerade as auth lock", () => {
  assert.match(accountSource, /"loading" \| "locked" \| "error" \| "ready"/);
  assert.match(accountSource, /response\.status === 401[\s\S]*setState\("locked"\)/);
  assert.match(accountSource, /load\(\)\.catch[\s\S]*setState\("error"\)/);
  assert.match(accountSource, /Provider accounts unavailable/);
});

test("provider account UI follows the global EN/VN locale", () => {
  assert.match(accountSource, /const \{ locale \} = useLocale\(\)/);
  assert.match(accountSource, /tr\("Sign in with the Dashboard API key\./);
  assert.match(accountSource, /tr\("Invalid admin key", "Admin key không đúng"\)/);
  assert.match(accountSource, /tr\("No cTrader accounts yet\./);
  assert.match(accountSource, /tr\("No MT5 accounts yet\./);
  assert.doesNotMatch(accountSource, /<p>Đăng nhập bằng Dashboard API key/);
});

test("one H1 surface owns both latest-day and Sunday-first retained-date navigation", () => {
  assert.match(h1EngineSource, /useLocale\(\)/);
  assert.match(h1EngineSource, /locale: serverLocale/);
  assert.match(h1EngineSource, /const \{ locale: liveLocale \} = useLocale\(\)/);
  assert.match(h1EngineSource, /<EngineCore data=\{h1Data\} degraded=\{degraded\} locale=\{locale\} \/>/);
  assert.match(h1EngineSource, /<H1SignalBoard data=\{h1Data\} degraded=\{degraded\} locale=\{locale\} \/>/);
  assert.doesNotMatch(h1EngineSource, /mode="live"|mode="history"/);
  assert.match(h1SignalSource, /function SundayCalendarPicker/);
  assert.match(h1SignalSource, /\[\"SUN\", \"MON\", \"TUE\", \"WED\", \"THU\", \"FRI\", \"SAT\"\]/);
  assert.match(h1SignalSource, /\[\"CN\", \"T2\", \"T3\", \"T4\", \"T5\", \"T6\", \"T7\"\]/);
  assert.match(h1SignalSource, /historyDatesForWeekday\(data\.days, \"all\"\)/);
  assert.match(h1SignalSource, /const date = data \? selectHistoryDate\(data\.days, "all", selectedDate\) : selectedDate/);
  assert.match(h1SignalSource, /<div className="oak-h1-history"/);
  assert.match(historyPageSource, /redirect\("\/engine"\)/);
  assert.doesNotMatch(historyPageSource, /readLatestH1Signals|HistoryClient/);
  assert.doesNotMatch(h1SignalSource, /type=\"date\"|HISTORY_FILTERS|weekdayFilter|oak-h1-history-options|Lọc theo thứ|Filter by weekday/);
  assert.doesNotMatch(enginePageSource, /DashboardAutoRefresh|router\.refresh/);
});

test("primary Tools tab follows LocaleProvider immediately without waiting for F5", () => {
  assert.match(toolsClientSource, /useLocale\(\)/);
  assert.match(toolsClientSource, /locale: serverLocale/);
  assert.match(toolsClientSource, /const \{ locale: liveLocale \} = useLocale\(\)/);
  assert.match(toolsClientSource, /tool\.name\[locale\]/);
  assert.match(toolsClientSource, /tool\.detail\[locale\]/);
  assert.match(toolsPageSource, /generateMetadata/);
  assert.match(toolsPageSource, /<ToolsClient locale=\{locale\} \/>/);
});

test("H1 entry cells stay centered, signal pills stay inside columns, and table headers remain aligned", () => {
  assert.match(h1SignalSource, /oak-h1-cell-entry/);
  assert.match(h1SignalSource, /scope="col"/);
  assert.match(h1SignalSource, /scope="row"/);
  assert.match(h1SignalSource, /id="h1-entry-time-row"/);
  assert.match(h1SignalSource, /headers=\{`h1-entry-time-row h1-hour-\$\{hour\}`\}/);
  assert.match(h1SignalSource, /oak-h1-cell-evidence/);
  assert.doesNotMatch(h1SignalSource, /VIP required|oak-h1-cell-locked/);
  assert.match(oakCss, /\.oak-h1-cell-entry[\s\S]*display: grid/);
  assert.match(oakCss, /\.oak-h1-cell-entry[\s\S]*text-align: center/);
  assert.match(oakCss, /\.oak-h1-scroll-hint \{ display: block; color: var\(--oak-fg-muted\); font-size: \.625rem; \}/);
  assert.doesNotMatch(h1SignalSource, /M15 E-2:15 · H3 RULE/);
  assert.match(oakCss, /\.oak-h1-cell-signal \{[\s\S]*box-sizing: border-box;[\s\S]*width: min\(3\.4rem, calc\(100% - \.4rem\)\);[\s\S]*min-width: 0;/);
});

test("all custom trading and NeoTech dialogs use the shared keyboard focus trap", () => {
  assert.match(h1EvidenceSource, /const open = Boolean\(selection\);/);
  assert.match(h1EvidenceSource, /useDialogFocusTrap(?:<[^>]+>)?\(open && variant === "dialog", onClose\)/);
  assert.match(neoTechSource, /useDialogFocusTrap(?:<[^>]+>)?\(Boolean\(pairing\)/);
  assert.match(dialogHookSource, /event\.key === "Escape"/);
  assert.match(dialogHookSource, /event\.key !== "Tab"/);
  assert.match(dialogHookSource, /event\.shiftKey/);
});

test("H1 header stays simplified while free access removes VIP actions", () => {
  assert.doesNotMatch(h1EngineSource, /<small>PROFILE<\/small>/);
  assert.match(h1SignalSource, /FREE ACCESS/);
  assert.match(h1SignalSource, /All H1 entry-time cells unlocked/);
  assert.doesNotMatch(h1EngineSource, /VIP UNLOCK|VIP LOCKED|oak-button-spinner|\/api\/vip/);
});

test("NeoTech and shared FactCheck states follow the global locale", () => {
  assert.match(neoTechSource, /useLocale\(\)/);
  assert.match(neoTechSource, /ToastState/);
  assert.match(neoTechSource, /styles\.toast/);
  assert.match(neoTechSource, /fmtDate\(profile\.generatedAtUtc, locale\)/);
  assert.match(factCheckSharedSource, /detectServerLocaleFromCookie/);
  assert.doesNotMatch(factCheckSharedSource, /const locale: "VN" \| "EN" = "VN"/);
});

test("shared FactCheck result uses the current workspace theme and balanced public layout", () => {
  assert.match(factCheckSharedSource, /factcheck-workspace\.module\.css/);
  assert.match(factCheckSharedSource, /styles\.routeShell/);
  assert.match(factCheckSharedSource, /factcheck-route-shell page-shell oak-fact-screen/);
  assert.ok((factCheckSharedSource.match(/styles\.routeShell/g) || []).length >= 2);
  assert.match(factCheckWorkspaceCss, /\.routeShell \{[\s\S]*--fact-canvas: var\(--engine-canvas/);
  assert.match(factCheckWorkspaceCss, /\.primaryAction \{[\s\S]*color: var\(--fact-canvas\)/);
  assert.doesNotMatch(factCheckWorkspaceCss, /color: #092117/);
  assert.match(oakCss, /\.oak-section-head :is\(h2,h3\)/);
  assert.match(oakCss, /\.oak-source-card :is\(h3,h4\)/);
  assert.match(factCheckPublicSource, /oak-public-confidence/);
  assert.match(factCheckPublicSource, /oak-public-result-metrics/);
  assert.match(factCheckPublicSource, /function cleanPublicText/);
  assert.match(factCheckPublicSource, /&\(\?:amp;\)\?nbsp;/);
  assert.match(factCheckShareCss, /\.oak-fact-public-text \.oak-verdict-panel \{[\s\S]*grid-template-columns: minmax\(0, 1fr\) auto/);
  assert.match(factCheckShareCss, /\.oak-fact-public \.oak-source-grid \{[\s\S]*grid-template-columns: repeat\(2, minmax\(0, 1fr\)\)/);
  assert.match(factCheckShareCss, /@media \(max-width: 760px\)[\s\S]*\.oak-fact-public-text \.oak-verdict-panel[\s\S]*grid-template-columns: minmax\(0, 1fr\)/);
  assert.match(factCheckShareCss, /@media \(max-width: 760px\)[\s\S]*\.oak-fact-public \.oak-source-grid[\s\S]*grid-template-columns: minmax\(0, 1fr\)/);
});

test("spatial HUD layer stays below DOM UI and respects performance guards", () => {
  assert.match(layoutSource, /<SpatialHudCanvas \/>/);
  assert.match(spatialSource, /getContext\("webgl"/);
  assert.match(spatialSource, /pointer-events: none|oak-spatial-stage/);
  assert.match(spatialSource, /visibilitychange/);
  assert.match(spatialSource, /prefers-reduced-motion: reduce/);
  assert.match(spatialSource, /MOBILE_HUD_QUERY = "\(max-width: 899px\), \(pointer: coarse\)"/);
  assert.match(spatialSource, /canvas\.dataset\.mobileDisabled = "true"/);
  assert.match(spatialSource, /powerPreference: "low-power"/);
  assert.match(spatialSource, /requestAnimationFrame/);
  assert.match(oakCss, /\.oak-spatial-stage \{/);
  assert.match(oakCss, /pointer-events: none/);
  assert.match(oakCss, /\.oak-main, \.oak-footer \{ position: relative; z-index: 1; \}/);
  assert.match(oakCss, /radial-gradient\(600px circle at var\(--hud-pointer-x\) var\(--hud-pointer-y\)/);
  assert.match(oakCss, /backdrop-filter: var\(--hud-glass-blur\)/);
  assert.match(oakCss, /@media \(max-width: 899px\), \(pointer: coarse\)/);
  assert.match(oakCss, /\.oak-spatial-stage \{ display: none !important; \}/);
  assert.match(oakCss, /body\.oak-body \{ background: var\(--oak-bg-canvas\) !important; \}/);
});

test("mobile engine geometry keeps horizontal, vertical and diagonal Orbit 3D motion while NeoTech advanced setup content cannot overlap", () => {
  assert.match(oakCss, /\.engine-core-orbit-horizontal \{ animation: engine-orbit-horizontal 10s linear infinite/);
  assert.match(oakCss, /\.engine-core-orbit-vertical \{[^}]*animation: engine-orbit-vertical 8s linear infinite/);
  assert.match(oakCss, /\.engine-core-orbit-diagonal \{[^}]*animation: engine-orbit-diagonal 13s linear infinite reverse/);
  assert.match(oakCss, /@keyframes engine-orbit-vertical/);
  assert.match(oakCss, /rotateY\(68deg\) rotateX\(360deg\)/);
  assert.match(oakCss, /\.engine-core-sphere \{[^}]*animation: engine-sphere-drift 18s ease-in-out infinite alternate/);
  assert.doesNotMatch(oakCss, /prefers-reduced-motion: reduce\), \(max-width: 759px\), \(pointer: coarse\)[^}]*engine-core-orbit[^}]*animation: none/);
  assert.match(oakCss, /@media \(prefers-reduced-motion: reduce\) \{\s*\.engine-core-orbit-horizontal, \.engine-core-orbit-vertical, \.engine-core-orbit-diagonal, \.engine-core-sphere \{ animation: none; \}/);
  assert.match(neotechCss, /\.downloadInstall details \{[^}]*min-width: 0;[^}]*overflow: visible/);
  assert.match(neotechCss, /\.downloadInstall details a \{[^}]*display: inline-flex;[^}]*max-width: 100%;[^}]*white-space: normal/);
  assert.match(neotechCss, /@media \(max-width: 760px\) \{[\s\S]*\.downloadInstall \{ align-content: start; \}/);
  assert.match(neotechCss, /\.ruleGroupLabel small \{[^}]*min-width: 0/);
});

test("desktop spatial grid uses a stronger two-scale perspective plane without re-enabling mobile HUD", () => {
  assert.match(globalsCss, /--hud-grid-accent: color-mix\(in srgb, var\(--oak-accent-command\) 20%, transparent\)/);
  assert.match(globalsCss, /--hud-grid-accent: rgba\(77, 159, 255, \.22\)/);
  assert.match(oakCss, /\.oak-spatial-grid \{[\s\S]*opacity: \.56/);
  assert.match(oakCss, /perspective\(720px\) rotateX\(66deg\) translateY\(8vh\) scale\(1\.08\)/);
  assert.match(oakCss, /background-size: 44px 44px, 44px 44px, 176px 176px, 176px 176px, 100% 100%/);
  assert.match(oakCss, /\.oak-spatial-grid::after/);
  assert.match(oakCss, /:root:not\(\.dark\):not\(\.contrast\) \.oak-spatial-grid \{ opacity: \.44; \}/);
  assert.match(oakCss, /@media \(max-width: 899px\), \(pointer: coarse\)[\s\S]*\.oak-spatial-stage \{ display: none !important; \}/);
});

test("legacy history route redirects to unified H1 while nested routes keep skip/breadcrumb context", () => {
  assert.doesNotMatch(navSource, /href="\/history"/);
  assert.match(historyPageSource, /redirect\("\/engine"\)/);
  assert.doesNotMatch(historyPageSource, /readLatestH1Signals|HistoryClient/);
  assert.match(layoutSource, /oak-skip-link/);
  assert.match(layoutSource, /id="main-content"/);
  assert.match(layoutSource, /<RouteBreadcrumbs \/>/);
  assert.match(breadcrumbSource, /pathname\.startsWith\("\/factcheck\/"\)/);
  assert.match(breadcrumbSource, /pathname\.startsWith\("\/neotech\/"\)/);
  assert.match(layoutSource, /oak-footer/);
});

test("technical labels use the shared 12px readability floor and tools menu has an explicit close action", () => {
  assert.match(navSource, /oak-tools-close/);
  assert.match(oakCss, /\.oak-tools-close/);
  assert.match(globalsCss, /--oak-text-base: \.875rem/);
  assert.match(globalsCss, /--oak-text-secondary: \.8125rem/);
  assert.match(globalsCss, /--oak-text-meta: \.75rem/);
  assert.match(oakCss, /\/\* Readability pass[\s\S]*\.oak-eyebrow,[\s\S]*\.oak-breadcrumb-inner \{ font-size: var\(--oak-text-meta\); \}/);
  assert.match(oakCss, /padding-left: max\(\.85rem, env\(safe-area-inset-left\)\)/);
});

test("Tarot controls keep domain and spread groups in distinct responsive grid rows", () => {
  assert.match(tarotSource, /fieldset className="tarot-domain-fieldset"/);
  assert.match(tarotSource, /fieldset className="tarot-spread-fieldset"/);
  assert.match(oakCss, /\.tarot-domain-fieldset \{ grid-row: 3; \}/);
  assert.match(oakCss, /\.tarot-spread-fieldset \{ grid-row: 4; \}/);
  assert.match(oakCss, /\.tarot-spread-options \{ display: grid; grid-template-columns: repeat\(2,minmax\(0,1fr\)\)/);
  assert.doesNotMatch(oakCss, /\.tarot-form fieldset \{[^}]*grid-column: 2;[^}]*grid-row: 1/);
  assert.doesNotMatch(oakCss, /\.tarot-form fieldset \{[^}]*grid-row: 3/);
});

test("mobile controls and calendar expose 44px-class touch targets", () => {
  assert.match(globalsCss, /--oak-touch-min: 2\.75rem/);
  assert.match(oakCss, /\.oak-theme-toggle \{[^}]*width: var\(--oak-touch-min\); height: var\(--oak-touch-min\)/);
  assert.match(oakCss, /grid-template-columns: repeat\(7, var\(--oak-touch-min\)\)/);
  assert.match(oakCss, /\.oak-h1-calendar-grid button \{[\s\S]*width: var\(--oak-touch-min\);[\s\S]*height: var\(--oak-touch-min\)/);
  assert.match(oakCss, /\.oak-locale-switch button \{[\s\S]*height: var\(--oak-touch-min\)/);
});

test("iPhone H1 surface stays inside the visual viewport and keeps native horizontal pan", () => {
  assert.match(oakCss, /iPhone\/Safari containment/);
  assert.match(oakCss, /\.oak-h1-table-scroll \{[\s\S]*overflow-x: scroll !important;[\s\S]*touch-action: pan-x pan-y;[\s\S]*-webkit-overflow-scrolling: touch/);
  assert.match(oakCss, /\.oak-h1-table-scroll \.oak-h1-table \{[\s\S]*width: 100%;[\s\S]*min-width: 100%;[\s\S]*table-layout: fixed/);
  assert.match(oakCss, /\.oak-h1-symbol-sticky \{ width: 5\.5rem !important; min-width: 5\.5rem; padding-inline: \.4rem; \}/);
  assert.match(oakCss, /\.oak-h1-calendar-popover \{[\s\S]*position: fixed;[\s\S]*right: max\(\.55rem, env\(safe-area-inset-right\)\);[\s\S]*left: max\(\.55rem, env\(safe-area-inset-left\)\);[\s\S]*transform: none/);
  assert.match(oakCss, /\.oak-h1-calendar-grid \{[\s\S]*grid-template-columns: repeat\(7, minmax\(0, 1fr\)\)/);
  assert.match(oakCss, /\.oak-engine-screen,[\s\S]*\.oak-h1-table-scroll \{[\s\S]*min-width: 0;[\s\S]*max-width: 100%/);
});

test("mobile H1 chrome stays compact and date changes reset the matrix to the first block", () => {
  assert.match(h1SignalSource, /useRef<HTMLDivElement>\(null\)/);
  assert.match(h1SignalSource, /scroller\.scrollLeft = 0/);
  assert.match(h1SignalSource, /\[date, hasData\]/);
  assert.match(h1SignalSource, /ref=\{tableScrollRef\} className="oak-h1-table-scroll lux-scroll"/);
  assert.match(oakCss, /Mobile density pass/);
  assert.match(oakCss, /\.nav-shell \{[\s\S]*padding-left: max\(\.55rem, env\(safe-area-inset-left\)\)/);
  assert.match(navSource, /<strong>OAK GATEKEEPER<\/strong>/);
  assert.match(oakCss, /\.oak-h1-board-head \{[^}]*padding: \.6rem/);
  assert.doesNotMatch(navSource, /<strong>ROBOT SLTP/);
});

test("light accent and signal states use stronger accessible visual treatment", () => {
  assert.match(globalsCss, /--oak-accent-command: #075ec8/);
  assert.match(globalsCss, /--oak-accent-command-strong: #004aa3/);
  assert.match(oakCss, /\.oak-h1-cell-signal \{[\s\S]*border-radius: 999px/);
  assert.match(oakCss, /\.oak-h1-cell-signal\[data-side="buy"\] \{ background: color-mix/);
  assert.match(oakCss, /\.oak-h1-cell-signal\[data-side="sell"\] \{ background: color-mix/);
  assert.match(oakCss, /\.oak-h1-block-invert-badge,[\s\S]*border-radius: 999px/);
});

test("provider account empty states expose immediate actions", () => {
  assert.match(accountSource, /id="oak-add-mt5"/);
  assert.match(accountSource, /Connect cTrader/);
  assert.match(accountSource, /href="#oak-add-mt5"/);
  assert.match(oakCss, /\.oak-account-empty button,/);
});

test("light theme keeps strong text, borders and opaque H1 surfaces over the desktop spatial layer", () => {
  assert.match(globalsCss, /--oak-fg-primary: #0b1220/);
  assert.match(globalsCss, /--oak-fg-muted: #475467/);
  assert.match(globalsCss, /--oak-border-subtle: #b8c2cf/);
  assert.match(globalsCss, /--hud-glass-bg: color-mix\(in srgb, var\(--oak-bg-surface\) 96%, transparent\)/);
  assert.match(oakCss, /:root:not\(\.dark\):not\(\.contrast\) \.oak-spatial-stage/);
  assert.match(oakCss, /:root:not\(\.dark\):not\(\.contrast\) \.oak-h1-table thead th/);
  assert.match(oakCss, /:root:not\(\.dark\):not\(\.contrast\) \.oak-h1-table tbody td/);
  assert.match(oakCss, /:root:not\(\.dark\):not\(\.contrast\) \.oak-h1-calendar-picker/);
});

test("NeoTech consumes the global semantic theme tokens instead of fixed dark and light islands", () => {
  const neoCss = readFileSync(new URL("../app/neotech/neotech.module.css", import.meta.url), "utf8");
  assert.match(neoCss, /--nt-canvas: var\(--oak-bg-canvas\)/);
  assert.match(neoCss, /--nt-surface: var\(--oak-bg-surface\)/);
  assert.match(neoCss, /--nt-border: var\(--oak-border-subtle\)/);
  assert.match(neoCss, /--nt-text: var\(--oak-fg-primary\)/);
  assert.match(neoCss, /--nt-muted: var\(--oak-fg-muted\)/);
  assert.match(neoCss, /--nt-blue: var\(--oak-accent-command\)/);
  assert.match(neoCss, /\.heroV2 \{[^}]*border: 1px solid var\(--nt-border\);[^}]*background:[^;}]*var\(--nt-surface\)/);
  assert.match(neoCss, /\.rulesetV2 \{[^}]*background: var\(--nt-surface\)/);
  assert.match(neoCss, /\.ruleConceptCard \{[^}]*background: var\(--nt-raised\)/);
  assert.match(neoCss, /\.demoCard \{[^}]*background: var\(--oak-bg-surface\);[^}]*color: var\(--oak-fg-primary\)/);
  assert.match(neoCss, /\.demoFacts div \{[^}]*background: var\(--oak-bg-raised\)/);
  assert.match(neoCss, /\.demoDonut::after \{[^}]*background: var\(--oak-bg-surface\)/);
  assert.match(neoCss, /\.bottomShowcase \{[^}]*background: var\(--oak-bg-canvas\)/);
  assert.doesNotMatch(neoCss, /#f5f9ff|#eaf1f9|#0b1b32|#14233a|#51647e|#ced8e6/);
  assert.doesNotMatch(neoTechSource, /fill=\"#[0-9a-fA-F]{6}\"/);
});
