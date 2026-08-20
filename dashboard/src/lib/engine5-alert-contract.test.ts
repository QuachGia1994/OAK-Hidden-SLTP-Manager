import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const patternSource = readFileSync(new URL("./pattern5.ts", import.meta.url), "utf8");
const boardSource = readFileSync(new URL("../components/Pattern5Board.tsx", import.meta.url), "utf8");
const rules = JSON.parse(readFileSync(new URL("../../engine5-alert-rules.json", import.meta.url), "utf8"));

test("Engine5 public schema requires independent-H15 generation", () => {
  assert.match(patternSource, /PATTERN5_PUBLIC_SCHEMA = 16/);
  assert.match(patternSource, /payload\.schemaVersion !== PATTERN5_PUBLIC_SCHEMA/);
});

test("alert business rules stay backend-owned while React omits the retired alert table", () => {
  assert.deepEqual(rules.coreBlocks, [3, 6, 9, 12, 15]);
  assert.equal(rules.conditionalBlock, undefined);
  assert.equal(rules.entryReminderMinute, 11);
  assert.equal(rules.consecutiveSrStopCount, 2);
  assert.equal(rules.h15ActivationGroups, undefined);
  assert.deepEqual(rules.h3AssetDirectionPolicy, { GBP: "reverse", AUD: "reverse", CAD: "reverse", JPY: "normal", XAU: "normal" });
  assert.match(patternSource, /alerts: table\.alerts/);
  assert.doesNotMatch(boardSource, /table\.alerts|AlertTable|ENGINE5 ALERTS|oak-alert-/);
  assert.doesNotMatch(boardSource, /consecutiveSrStopCount|h15ActivationGroups|entryReminderMinute|h3AssetDirectionPolicy/);
});
