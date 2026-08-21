import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  assertUniqueProviderLabels,
  cTraderProviderAccountId,
  normalizeMt5Registration,
  normalizePositivePoints,
  parseCTraderProviderAccountId,
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

test("multi-provider web control plane is admin-only and does not expose broker secrets", () => {
  assert.match(routeSource, /requireAdminOrApiAuth/);
  assert.match(routeSource, /sync-ctrader/);
  assert.match(routeSource, /create-mt5/);
  assert.match(storeSource, /oak:provider-accounts:mt5:v1/);
  assert.match(storeSource, /oak:provider-accounts:default:v1/);
  assert.match(panelSource, /Connect cTrader/);
  assert.match(panelSource, /Add MT5 account/);
  assert.match(panelSource, /Metadata only/);
  assert.doesNotMatch(panelSource, /name="password"|name="accessToken"|name="refreshToken"|clientSecret/);
  assert.doesNotMatch(routeSource, /password\s*:/i);
});
