import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { lotsToProtocolVolume, mt5PointsToCTraderRelative } from "./ctrader-execution-domain.ts";

const oauthSource = readFileSync(new URL("../app/api/ctrader/oauth/route.ts", import.meta.url), "utf8");
const executionSource = readFileSync(new URL("./telegram-cloud-execution.ts", import.meta.url), "utf8");
const ctraderSource = readFileSync(new URL("./ctrader-json.ts", import.meta.url), "utf8");
const accountsSource = readFileSync(new URL("./ctrader-accounts.ts", import.meta.url), "utf8");
const adminAuthSource = readFileSync(new URL("./admin-auth.ts", import.meta.url), "utf8");

test("cTrader lot conversion uses symbol lotSize and rejects invalid volume steps", () => {
  const meta = { lotSize: 10_000_000, minVolume: 1_000, maxVolume: 100_000_000, stepVolume: 1_000 };
  assert.equal(lotsToProtocolVolume(0.01, meta), 100_000);
  assert.equal(lotsToProtocolVolume(0.1, meta), 1_000_000);
  assert.throws(() => lotsToProtocolVolume(0.01005, meta), /volume step/);
});

test("legacy MT5 points convert to cTrader relative price units by symbol digits", () => {
  assert.equal(mt5PointsToCTraderRelative(500, 5), 500);
  assert.equal(mt5PointsToCTraderRelative(1000, 2), 1_000_000);
  assert.equal(mt5PointsToCTraderRelative(500, 3), 50_000);
});

test("OAuth reconnect requests trading scope explicitly", () => {
  assert.match(oauthSource, /set\("scope", "trading"\)/);
  assert.match(oauthSource, /exchangeAuthorizationCode\(code, redirectUri, "trading"\)/);
});

test("execution boundary uses confirm-time snapshot protection and all target accounts", () => {
  assert.match(executionSource, /task\.protectionPlan/);
  assert.match(executionSource, /task\.targetAccountIds/);
  assert.match(executionSource, /placeCTraderMarketOrder/);
  assert.match(executionSource, /closeCTraderPositions/);
  assert.match(executionSource, /amendCTraderPositionProtection/);
  assert.match(executionSource, /automatic retry is disabled/);
});

test("account discovery queries both cTrader live and demo environments", () => {
  assert.match(ctraderSource, /environment: "live"/);
  assert.match(ctraderSource, /environment: "demo"/);
  assert.match(ctraderSource, /Promise\.all/);
  assert.match(ctraderSource, /fetchGrantedAccountsFromEnvironment/);
});

test("legacy profile alias cannot fan out silently across multiple enabled accounts", () => {
  assert.match(accountsSource, /if \(!needle\) return enabled/);
  assert.match(accountsSource, /enabled\.length === 1 \? enabled : \[\]/);
  assert.match(accountsSource, /item\.label\.trim\(\)\.toLowerCase\(\) === needle/);
});

test("managed account defaults preserve legacy SL TP point contract and unique labels", () => {
  assert.match(accountsSource, /fxSlPoints: 500/);
  assert.match(accountsSource, /fxTpPoints: 10000/);
  assert.match(accountsSource, /goldSlPoints: 1000/);
  assert.match(accountsSource, /goldTpPoints: 20000/);
  assert.match(accountsSource, /Duplicate account label/);
  assert.match(accountsSource, /SL\/TP points must be positive finite numbers/);
});

test("account admin cookie is signed with an embedded server-validated expiry", () => {
  assert.match(adminAuthSource, /SESSION_TTL_MS = 12 \* 60 \* 60 \* 1000/);
  assert.match(adminAuthSource, /sessionSignature\(expiresAt\)/);
  assert.match(adminAuthSource, /expiresAt <= nowMs/);
  assert.match(adminAuthSource, /timingSafeEqual/);
});
