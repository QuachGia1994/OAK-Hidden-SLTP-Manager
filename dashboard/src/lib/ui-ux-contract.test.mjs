import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const navSource = readFileSync(new URL("../components/NavBar.tsx", import.meta.url), "utf8");
const h1EngineSource = readFileSync(new URL("../components/H1EngineBoard.tsx", import.meta.url), "utf8");
const h1SignalSource = readFileSync(new URL("../components/H1SignalBoard.tsx", import.meta.url), "utf8");
const accountSource = readFileSync(new URL("../components/ProviderAccountsPanel.tsx", import.meta.url), "utf8");
const dialogHookSource = readFileSync(new URL("../hooks/useDialogFocusTrap.ts", import.meta.url), "utf8");
const neoTechSource = readFileSync(new URL("../app/neotech/NeoTechPublicDashboard.tsx", import.meta.url), "utf8");
const factCheckSharedSource = readFileSync(new URL("../app/factcheck/[id]/page.tsx", import.meta.url), "utf8");
const oakCss = readFileSync(new URL("../app/oak-redesign.css", import.meta.url), "utf8");

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

test("all custom trading and NeoTech dialogs use the shared keyboard focus trap", () => {
  assert.match(h1EngineSource, /useDialogFocusTrap\(open/);
  assert.match(h1SignalSource, /useDialogFocusTrap\(true/);
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
  assert.match(neoTechSource, /copyStatus/);
  assert.match(neoTechSource, /fmtDate\(profile\.generatedAtUtc, locale\)/);
  assert.match(factCheckSharedSource, /detectServerLocaleFromCookie/);
  assert.doesNotMatch(factCheckSharedSource, /const locale: "VN" \| "EN" = "VN"/);
});
