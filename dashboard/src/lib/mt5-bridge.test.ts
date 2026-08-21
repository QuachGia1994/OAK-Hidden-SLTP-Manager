import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { normalizeProviderAccountId } from "./telegram-cloud-domain.ts";

const bridge = readFileSync(new URL("./mt5-bridge.ts", import.meta.url), "utf8");
const localBridge = readFileSync(new URL("../../../domain/mt5_cloud_bridge.py", import.meta.url), "utf8");
const monitorWorker = readFileSync(new URL("../../../domain/monitor_worker.py", import.meta.url), "utf8");
const execution = readFileSync(new URL("./telegram-cloud-execution.ts", import.meta.url), "utf8");

test("legacy cTrader target ids migrate to namespaced provider ids", () => {
  assert.equal(normalizeProviderAccountId(12345), "ctrader:12345");
  assert.equal(normalizeProviderAccountId("12345"), "ctrader:12345");
  assert.equal(normalizeProviderAccountId("ctrader:12345"), "ctrader:12345");
  assert.equal(normalizeProviderAccountId("mt5:abcdefgh"), "mt5:abcdefgh");
  assert.equal(normalizeProviderAccountId("bad"), "");
});

test("MT5 cloud bridge has one durable claim boundary and no blind timeout replay", () => {
  assert.match(bridge, /ARBITER_PREFIX/);
  assert.match(bridge, /nx: true, ex: TASK_TTL_SECONDS/);
  assert.match(bridge, /claimed the task but no final broker result arrived before timeout; automatic retry is disabled/);
  assert.match(localBridge, /"SET", _arbiter_key\(task_id\), claim_token, "NX", "EX", TASK_TTL_SECONDS/);
  assert.match(localBridge, /send_order_idempotent/);
  assert.match(localBridge, /send_mutation_idempotent/);
});

test("MT5 mutation stays inside the owning MonitorWorker session", () => {
  assert.match(monitorWorker, /MT5CloudBridge/);
  assert.match(monitorWorker, /bridge_task = self\.mt5_cloud_bridge\.next_task\(\)/);
  assert.match(monitorWorker, /execute_mt5_bridge_task\(bridge_task, self\.config, mt5_module=mt5\)/);
  assert.match(localBridge, /validate_mt5_mutation_session/);
  assert.match(localBridge, /BRIDGE_LOGIN_MISMATCH/);
});

test("cloud execution routes both cTrader and MT5 without globally requiring cTrader OAuth", () => {
  assert.match(execution, /provider\.provider === "mt5"/);
  assert.match(execution, /executeMt5BridgeAction/);
  assert.match(execution, /placeCTraderMarketOrder/);
  assert.match(execution, /closeCTraderPositions/);
  assert.match(execution, /amendCTraderPositionProtection/);
  assert.ok(execution.indexOf("provider.provider === \"mt5\"") < execution.indexOf("getFreshCTraderTokens()"));
});
