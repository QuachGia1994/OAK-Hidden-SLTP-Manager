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
const oakCss = readFileSync(new URL("../app/oak-redesign.css", import.meta.url), "utf8");
const globalsCss = readFileSync(new URL("../app/globals.css", import.meta.url), "utf8");
const layoutSource = readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8");
const spatialSource = readFileSync(new URL("../components/SpatialHudCanvas.tsx", import.meta.url), "utf8");
const breadcrumbSource = readFileSync(new URL("../components/RouteBreadcrumbs.tsx", import.meta.url), "utf8");
const historyPageSource = readFileSync(new URL("../app/history/page.tsx", import.meta.url), "utf8");

test("mobile keeps locale reachable and exposes four direct navigation tabs", () => {
  assert.ok(navSource.includes("oak-locale-switch"));
  assert.ok(navSource.includes("setLocaleMode(item)"));
  assert.ok(navSource.includes("router.refresh()"));
  assert.ok(!navSource.includes("window.location.reload"));
  assert.ok(navSource.includes('href="/tools" className="oak-nav-link oak-tools-mobile-link"'));
  assert.doesNotMatch(navSource, /mobileOpen|oak-mobile-nav-toggle|data-mobile-open/);
  assert.ok(oakCss.includes(".oak-tools-mobile-link { display: inline-flex; }"));
  assert.ok(oakCss.includes("grid-template-columns: repeat(4,minmax(0,1fr))"));
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

test("H1 live stays latest-day only while History owns Sunday-first date navigation", () => {
  assert.match(h1SignalSource, /function SundayCalendarPicker/);
  assert.match(h1SignalSource, /\[\"SUN\", \"MON\", \"TUE\", \"WED\", \"THU\", \"FRI\", \"SAT\"\]/);
  assert.match(h1SignalSource, /\[\"CN\", \"T2\", \"T3\", \"T4\", \"T5\", \"T6\", \"T7\"\]/);
  assert.match(h1SignalSource, /historyDatesForWeekday\(data\.days, \"all\"\)/);
  assert.match(h1SignalSource, /historyMode \? selectHistoryDate\(data\.days, "all", selectedDate\) : latestDate/);
  assert.match(h1SignalSource, /\{historyMode && <div className="oak-h1-history"/);
  assert.match(h1EngineSource, /mode="live"/);
  assert.match(historyPageSource, /mode="history"/);
  assert.doesNotMatch(h1SignalSource, /type=\"date\"|HISTORY_FILTERS|weekdayFilter|oak-h1-history-options|Lọc theo thứ|Filter by weekday/);
  assert.doesNotMatch(enginePageSource, /DashboardAutoRefresh|router\.refresh/);
});

test("H1 entry cells stay centered, expose mobile scroll affordance and table header relationships", () => {
  assert.match(h1SignalSource, /oak-h1-cell-entry/);
  assert.match(h1SignalSource, /scope="col"/);
  assert.match(h1SignalSource, /scope="row"/);
  assert.match(h1SignalSource, /headers=\{`h1-symbol-\$\{base\} h1-hour-\$\{hour\}`\}/);
  assert.match(h1SignalSource, /oak-h1-cell-evidence/);
  assert.doesNotMatch(h1SignalSource, /VIP required|oak-h1-cell-locked/);
  assert.match(oakCss, /\.oak-h1-cell-entry[\s\S]*display: grid/);
  assert.match(oakCss, /\.oak-h1-cell-entry[\s\S]*text-align: center/);
  assert.match(oakCss, /\.oak-h1-scroll-hint \{ display: block; color: var\(--oak-fg-muted\); font-size: \.625rem; \}/);
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

test("history route is restored to primary navigation and nested routes keep skip/breadcrumb context", () => {
  assert.match(navSource, /href="\/history"/);
  assert.match(historyPageSource, /readLatestH1Signals/);
  assert.match(historyPageSource, /<H1SignalBoard/);
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
  assert.match(oakCss, /\.oak-h1-table-scroll \.oak-h1-table \{[\s\S]*width: max-content;[\s\S]*min-width: max-content/);
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
