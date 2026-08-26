import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync, statSync } from "node:fs";
import path from "node:path";

const dashboardRoot = process.cwd();
const repoRoot = path.resolve(dashboardRoot, "..");

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = path.join(dir, name);
    return statSync(full).isDirectory() ? walk(full) : [full];
  });
}

test("public NeoTech analytics source cannot import trading execution surfaces", () => {
  const roots = [
    path.join(dashboardRoot, "src", "app", "api", "neotech", "public"),
    path.join(dashboardRoot, "src", "app", "api", "neotech", "connector"),
  ];
  const files = [
    ...roots.flatMap(walk),
    ...walk(path.join(dashboardRoot, "src", "lib")).filter((file) => /neotech-public-(auth|domain|engine|service|store)\.ts$/.test(file)),
  ];
  const forbidden = [
    "mt5-bridge",
    "telegram-cloud-runner",
    "telegram-cloud-store",
    "ctrader-execution",
    "executeMt5BridgeAction",
    "runCloudIntentExecution",
    "createCloudIntent",
  ];
  for (const file of files) {
    const text = readFileSync(file, "utf8");
    for (const token of forbidden) assert.equal(text.includes(token), false, `${path.relative(repoRoot, file)} must not reference ${token}`);
  }
});

test("public MT5 connector remains structurally non-trading even when Master access is explicitly accepted", () => {
  const sourcePath = path.join(repoRoot, "mt5", "OAK_NeoTech_ReadOnly_Connector.mq5");
  const source = readFileSync(sourcePath, "utf8");
  const forbidden = ["#include <Trade/", "CTrade", "OrderSend(", "OrderSendAsync(", ".Buy(", ".Sell(", "PositionClose(", "PositionModify(", "OrderDelete("];
  for (const token of forbidden) assert.equal(source.includes(token), false, `telemetry connector must not contain ${token}`);
  assert.match(source, /ACCOUNT_TRADE_ALLOWED/);
  assert.match(source, /Investor Password/);
  assert.match(source, /TRADING_CAPABLE_ACCEPTED/);
  assert.match(source, /g_pair_code_hash/);
  assert.match(source, /legacy_master_upgrade=loaded && g_pair_code_hash=="" && requested_hash!="" && capability_mismatch/);
  assert.match(source, /fresh_code=loaded && capability_mismatch && g_pair_code_hash!="" && requested_hash!="" && requested_hash!=g_pair_code_hash/);
  assert.match(source, /must_pair=!loaded \|\| fresh_code \|\| legacy_master_upgrade/);
  assert.match(source, /readonly_"\+IntegerToString\(\(long\)AccountInfoInteger\(ACCOUNT_LOGIN\)\)\+"_"\+OakCredentialIdentityHash\(\)/);
  assert.match(source, /g_loaded_legacy_credentials/);
  assert.match(source, /OakCredentialUnauthorizedResponse/);
  assert.match(source, /OakDeleteCredentialFileIfMatches/);
  assert.match(source, /g_sync_enabled=false/);
  assert.match(source, /revoked or purged/);
  assert.match(source, /WAITING_PAIR state/);
  assert.match(source, /WAITING_AUTHORIZATION state/);
  assert.match(source, /return INIT_SUCCEEDED/);
  assert.doesNotMatch(source, /attach again/);
  assert.match(source, /WebRequest\(/);
});

test("Master pairing is browser-authorized and NeoTech Copy actions expose visible toast feedback", () => {
  const pairingRoute = readFileSync(path.join(dashboardRoot, "src", "app", "api", "neotech", "public", "pairing", "route.ts"), "utf8");
  const ui = readFileSync(path.join(dashboardRoot, "src", "app", "neotech", "NeoTechPublicDashboard.tsx"), "utf8");
  assert.match(pairingRoute, /TRADING_CAPABLE_ACCEPTED/);
  assert.match(pairingRoute, /riskAccepted !== true/);
  assert.match(ui, /MASTER PASSWORD WARNING/);
  assert.match(ui, /Master Password risk accepted/);
  assert.match(ui, /styles\.toast/);
  assert.match(ui, /createPortal/);
  assert.match(ui, /document\.body/);
  assert.match(ui, /Pairing code copied/);
  assert.match(ui, /WebRequest URL copied/);
});
