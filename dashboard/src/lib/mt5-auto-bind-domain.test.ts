import test from "node:test";
import assert from "node:assert/strict";
import {
  createMt5AutoBindRecord,
  mt5AutoBindExactKey,
  mt5AutoBindLoginKey,
  mt5ServerHash,
} from "./mt5-auto-bind-domain.ts";

test("MT5 auto-bind exact identity is stable across server whitespace/case", () => {
  assert.equal(mt5ServerHash("  Broker-Live  "), mt5ServerHash("broker-live"));
  assert.equal(mt5AutoBindExactKey(123456, "Broker-Live"), mt5AutoBindExactKey(123456, " broker-live "));
  assert.match(mt5AutoBindExactKey(123456, "Broker-Live"), /^oak:mt5:bridge:auto-bind:v1:exact:123456:[a-f0-9]{40}$/);
});

test("MT5 auto-bind login fallback is deterministic", () => {
  assert.equal(mt5AutoBindLoginKey(123456), "oak:mt5:bridge:auto-bind:v1:login:123456");
  assert.throws(() => mt5AutoBindLoginKey(0), /positive integer/);
});

test("MT5 auto-bind record carries immutable account routing identity", () => {
  const record = createMt5AutoBindRecord({
    id: "mt5:abcdefgh",
    login: 123456,
    bridgeProfile: "FXCE",
    bridgeServer: "Broker-Live",
  });
  assert.deepEqual(record, {
    version: 1,
    providerAccountId: "mt5:abcdefgh",
    bridgeProfile: "FXCE",
    login: 123456,
    serverHash: mt5ServerHash("Broker-Live"),
  });
});
