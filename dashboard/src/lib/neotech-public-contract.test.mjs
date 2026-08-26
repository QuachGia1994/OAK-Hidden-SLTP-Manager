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

test("public MT5 connector is structurally read-only", () => {
  const sourcePath = path.join(repoRoot, "mt5", "OAK_NeoTech_ReadOnly_Connector.mq5");
  const source = readFileSync(sourcePath, "utf8");
  const forbidden = ["#include <Trade/", "CTrade", "OrderSend(", "OrderSendAsync(", ".Buy(", ".Sell(", "PositionClose(", "PositionModify(", "OrderDelete("];
  for (const token of forbidden) assert.equal(source.includes(token), false, `read-only connector must not contain ${token}`);
  assert.match(source, /ACCOUNT_TRADE_ALLOWED/);
  assert.match(source, /Investor Password/);
  assert.match(source, /WebRequest\(/);
});
