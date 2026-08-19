import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const patternSource = readFileSync(new URL("./pattern5.ts", import.meta.url), "utf8");
const boardSource = readFileSync(new URL("../components/Pattern5Board.tsx", import.meta.url), "utf8");
const rules = JSON.parse(readFileSync(new URL("../../engine5-alert-rules.json", import.meta.url), "utf8"));

test("Engine5 public schema rejects unconditional-H15 generation", () => {
  assert.match(patternSource, /PATTERN5_PUBLIC_SCHEMA = 15/);
  assert.match(patternSource, /payload\.schemaVersion !== PATTERN5_PUBLIC_SCHEMA/);
});

test("alert business rules have one JSON owner and React renders typed codes only", () => {
  assert.deepEqual(rules.coreBlocks, [3, 6, 9, 12]);
  assert.equal(rules.conditionalBlock, 15);
  assert.equal(rules.entryReminderMinute, 11);
  assert.equal(rules.consecutiveSrStopCount, 2);
  assert.deepEqual(rules.h15ActivationGroups, ["Sw", "Sr"]);
  assert.deepEqual(rules.h3AssetDirectionPolicy, { GBP: "reverse", AUD: "reverse", CAD: "reverse", JPY: "normal", XAU: "normal" });
  assert.match(boardSource, /table\.alerts/);
  assert.doesNotMatch(boardSource, /consecutiveSrStopCount|h15ActivationGroups|entryReminderMinute|h3AssetDirectionPolicy/);
});

test("web alert copy is complete in EN and VN", () => {
  for (const code of ["h3_reverse_signal", "h3_normal_signal", "sr_entry_at_11", "consecutive_sr_stop", "h15_armed", "h15_inactive"]) {
    assert.ok(boardSource.includes(code), code);
  }
  assert.match(boardSource, /STOP TRADING/);
  assert.match(boardSource, /NGƯNG GIAO DỊCH/);
  assert.match(boardSource, /H15 inactive/);
  assert.match(boardSource, /H15 không kích hoạt/);
});
