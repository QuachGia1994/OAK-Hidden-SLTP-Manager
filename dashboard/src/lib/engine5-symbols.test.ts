import assert from "node:assert/strict";
import test from "node:test";
import { ENGINE5_ACTIVE_SYMBOLS, filterActiveEngine5Tables, isActiveEngine5Symbol } from "./engine5-symbols.ts";

test("Engine5 active symbol scope is GBPUSD only", () => {
  assert.deepEqual([...ENGINE5_ACTIVE_SYMBOLS], ["GBPUSD"]);
  assert.equal(isActiveEngine5Symbol("GBPUSD"), true);
  assert.equal(isActiveEngine5Symbol("EURUSD"), false);
});

test("legacy payload tables keep GBPUSD and suppress inactive EURUSD", () => {
  const legacy = [
    { base: "GBPUSD", rows: { "3": [] } },
    { base: "EURUSD", rows: { "3": [] } },
  ];
  assert.deepEqual(filterActiveEngine5Tables(legacy).map((table) => table.base), ["GBPUSD"]);
});
