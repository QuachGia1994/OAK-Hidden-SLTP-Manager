import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const bridge = readFileSync(new URL("./mt5-bridge.ts", import.meta.url), "utf8");

test("production MT5 bridge task envelope is pinned to schema v2", () => {
  assert.match(bridge, /export const MT5_BRIDGE_TASK_VERSION = 2 as const;/);
  assert.match(bridge, /version: typeof MT5_BRIDGE_TASK_VERSION;/);
  assert.match(bridge, /version: MT5_BRIDGE_TASK_VERSION,/);
  assert.match(bridge, /current\.version !== MT5_BRIDGE_TASK_VERSION/);
  assert.match(bridge, /originKey\?: string;/);
  assert.match(bridge, /ledgerKey\?: string;/);
  assert.match(bridge, /taskDigest: string;/);
  assert.doesNotMatch(bridge, /version:\s*1[;,]/);
});
