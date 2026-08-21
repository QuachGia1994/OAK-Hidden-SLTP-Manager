import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  assertUniqueProviderLabels,
  cTraderProviderAccountId,
  normalizeMt5Registration,
  normalizePositivePoints,
  parseCTraderProviderAccountId,
  providerProtectionPoints,
  resolveEnabledProviderTargets,
  type ProviderAccountSummary,
} from "./provider-account-domain.ts";

const panelSource = readFileSync(new URL("../components/ProviderAccountsPanel.tsx", import.meta.url), "utf8");
const routeSource = readFileSync(new URL("../app/api/accounts/route.ts", import.meta.url), "utf8");
const storeSource = readFileSync(new URL("./provider-accounts.ts", import.meta.url), "utf8");

test("provider account ids keep cTrader namespace explicit", () => {
  assert.equal(cTraderProviderAccountId(123456), "ctrader:123456");
  assert.equal(parseCTraderProviderAccountId("ctrader:123456"), 123456);
  assert.equal(parseCTraderProviderAccountId("mt5:123456"), null);
  assert.throws(() => cTraderProviderAccountId(0));
});

test("MT5 registration normalizes metadata without accepting secret fields", () => {
  const row = normalizeMt5Registration({
    broker: "  Vantage   Markets ",
    environment: "live",
    login: 778899,
    label: " Main   Vantage ",
    bridgeProfile: " Vantage ",
  });
  assert.equal(row.broker, "Vantage Markets");
  assert.equal(row.label, "Main Vantage");
  assert.equal(row.bridgeProfile, "Vantage");
  assert.equal(row.login, 778899);
  assert.equal(row.fxSlPoints, 500);
  assert.equal(row.goldTpPoints, 20000);
});

test("protection points and labels fail closed", () => {
  assert.equal(normalizePositivePoints(undefined, 500), 500);
  assert.throws(() => normalizePositivePoints(0, 500));
  assert.throws(() => normalizePositivePoints(Number.NaN, 500));
  assert.throws(() => assertUniqueProviderLabels([
    { id: "ctrader:1", label: "Main" },
    { id: "mt5:a", label: "Backup" },
  ], " main ", "mt5:a"));
});

test("provider routing selects explicit bridge profiles and otherwise fans out to enabled accounts", () => {
  const accounts: ProviderAccountSummary[] = [
    { id: "ctrader:11", provider: "ctrader", broker: "ICMarkets", environment: "live", externalAccountId: "11", traderLogin: 101, label: "cTrader Main", enabled: true, isDefault: false, connectionMode: "oauth", bridgeProfile: null, fxSlPoints: 500, fxTpPoints: 10000, goldSlPoints: 1000, goldTpPoints: 20000, updatedAt: 1 },
    { id: "mt5:abcdefgh", provider: "mt5", broker: "Vantage", environment: "live", externalAccountId: "202", traderLogin: 202, label: "MT5 Main", enabled: true, isDefault: false, connectionMode: "bridge", bridgeProfile: "Vantage", fxSlPoints: 600, fxTpPoints: 12000, goldSlPoints: 1200, goldTpPoints: 22000, updatedAt: 1 },
  ];
  assert.deepEqual(resolveEnabledProviderTargets(accounts).map((item) => item.id), ["ctrader:11", "mt5:abcdefgh"]);
  assert.deepEqual(resolveEnabledProviderTargets(accounts, "Vantage").map((item) => item.id), ["mt5:abcdefgh"]);
  const ambiguous = accounts.map((item) => ({ ...item, externalAccountId: "202" }));
  assert.deepEqual(resolveEnabledProviderTargets(ambiguous, "202"), []);
  assert.deepEqual(providerProtectionPoints(accounts[1], "XAUUSD"), { sl: 1200, tp: 22000 });
  assert.deepEqual(providerProtectionPoints(accounts[1], "GBPUSD"), { sl: 600, tp: 12000 });
});

test("multi-provider web control plane is admin-only and does not expose broker secrets", () => {
  assert.match(routeSource, /requireAdminOrApiAuth/);
  assert.match(routeSource, /sync-ctrader/);
  assert.match(routeSource, /create-mt5/);
  assert.match(storeSource, /oak:provider-accounts:mt5:v1/);
  assert.match(storeSource, /oak:provider-accounts:default:v1/);
  assert.match(panelSource, /Connect cTrader/);
  assert.match(panelSource, /Add MT5 account/);
  assert.match(panelSource, /outbound bridge/);
  assert.doesNotMatch(panelSource, /name="password"|name="accessToken"|name="refreshToken"|clientSecret/);
  assert.doesNotMatch(routeSource, /password\s*:/i);
});
