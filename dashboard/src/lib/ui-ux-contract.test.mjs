import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const navSource = readFileSync(new URL("../components/NavBar.tsx", import.meta.url), "utf8");
const h1EngineSource = readFileSync(new URL("../components/H1EngineBoard.tsx", import.meta.url), "utf8");
const h1SignalSource = readFileSync(new URL("../components/H1SignalBoard.tsx", import.meta.url), "utf8");
const enginePageSource = readFileSync(new URL("../app/engine/page.tsx", import.meta.url), "utf8");
const accountSource = readFileSync(new URL("../components/ProviderAccountsPanel.tsx", import.meta.url), "utf8");
const dialogHookSource = readFileSync(new URL("../hooks/useDialogFocusTrap.ts", import.meta.url), "utf8");
const neoTechSource = readFileSync(new URL("../app/neotech/NeoTechPublicDashboard.tsx", import.meta.url), "utf8");
const factCheckSharedSource = readFileSync(new URL("../app/factcheck/[id]/page.tsx", import.meta.url), "utf8");
const oakCss = readFileSync(new URL("../app/oak-redesign.css", import.meta.url), "utf8");
const layoutSource = readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8");
const spatialSource = readFileSync(new URL("../components/SpatialHudCanvas.tsx", import.meta.url), "utf8");

test("mobile keeps the global locale switch reachable", () => {
  assert.match(navSource, /oak-locale-switch/);
  assert.match(navSource, /setLocaleMode\(item\)/);
  assert.doesNotMatch(oakCss, /\.oak-locale-switch\s*\{\s*display:\s*none/);
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

test("H1 dashboard keeps date navigation without weekday filter controls", () => {
  assert.match(h1SignalSource, /type=\"date\"/);
  assert.match(h1SignalSource, /historyDatesForWeekday\(data\.days, \"all\"\)/);
  assert.doesNotMatch(h1SignalSource, /HISTORY_FILTERS|weekdayFilter|oak-h1-history-options|Lọc theo thứ|Filter by weekday/);
  assert.doesNotMatch(enginePageSource, /DashboardAutoRefresh|router\.refresh/);
});

test("H1 signal cells stay centered and use an explicit compact type scale", () => {
  assert.match(h1SignalSource, /oak-h1-cell-signal/);
  assert.match(oakCss, /\.oak-h1-cell-signal[\s\S]*display: grid/);
  assert.match(oakCss, /\.oak-h1-cell-signal[\s\S]*text-align: center/);
});

test("all custom trading and NeoTech dialogs use the shared keyboard focus trap", () => {
  assert.match(h1EngineSource, /useDialogFocusTrap\(open/);
  assert.match(neoTechSource, /useDialogFocusTrap(?:<[^>]+>)?\(Boolean\(pairing\)/);
  assert.match(dialogHookSource, /event\.key === "Escape"/);
  assert.match(dialogHookSource, /event\.key !== "Tab"/);
  assert.match(dialogHookSource, /event\.shiftKey/);
});

test("H1 header stays simplified and VIP logout errors remain visible", () => {
  assert.doesNotMatch(h1EngineSource, /<small>PROFILE<\/small>/);
  assert.match(h1EngineSource, /!open && error/);
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
  assert.match(spatialSource, /pointer: coarse/);
  assert.match(spatialSource, /powerPreference: "low-power"/);
  assert.match(spatialSource, /requestAnimationFrame/);
  assert.match(oakCss, /\.oak-spatial-stage \{/);
  assert.match(oakCss, /pointer-events: none/);
  assert.match(oakCss, /\.oak-main, \.oak-footer, \.oak-nav \{ position: relative; z-index: 1; \}/);
  assert.match(oakCss, /radial-gradient\(600px circle at var\(--hud-pointer-x\) var\(--hud-pointer-y\)/);
  assert.match(oakCss, /backdrop-filter: var\(--hud-glass-blur\)/);
  assert.match(oakCss, /\.oak-android \.oak-spatial-canvas/);
});
