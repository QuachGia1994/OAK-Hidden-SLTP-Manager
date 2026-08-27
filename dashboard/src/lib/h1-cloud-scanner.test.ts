import assert from "node:assert/strict";
import test from "node:test";

import {
  H1_CLOUD_STATE_VERSION,
  H1_SCAN_HOURS,
  H1_SIGNAL_RULE_VERSION,
  H1_TARGET_BASES,
  baseSymbolForTarget,
  baseSymbolForTargetSlot,
  buildPublicFeed,
  buildStoredAlert,
  emptyCloudState,
  findH1PatternMatchesForTarget,
  parseCloudState,
  postSignalDecision,
  scannerBaseForTarget,
  type H1Direction,
  type H1DirectionBar,
  type H1PatternKind,
} from "./h1-cloud-scanner.ts";

function barsFromOldest(sequence: string, startHour = 0, date = "2026-08-17"): H1DirectionBar[] {
  return [...sequence].map((direction, index) => ({
    hour: startHour + index,
    brokerDate: date,
    brokerTime: `${date}T${String(startHour + index).padStart(2, "0")}:00`,
    direction: direction as H1Direction,
  }));
}

function barsForPattern(patternNewestFirst: string, slotHour: number, date = "2026-08-17"): H1DirectionBar[] {
  return barsFromOldest([...patternNewestFirst].reverse().join(""), slotHour - patternNewestFirst.length, date);
}

test("five-pattern grid owns one fixed six-slot schedule", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 45);
  assert.equal(H1_SIGNAL_RULE_VERSION, 39);
  assert.deepEqual(H1_SCAN_HOURS, [3, 6, 9, 12, 14, 16]);

  const dayBars = barsFromOldest("TGTGGTTGTGGTTGTT", 0);
  for (const base of H1_TARGET_BASES) {
    assert.deepEqual(
      findH1PatternMatchesForTarget(base, dayBars, 16).map((match) => match.slotHour),
      H1_SCAN_HOURS,
    );
  }
});

test("all five scanner pattern classes are explicit and exhaustive", () => {
  const cases: Array<[string, H1PatternKind]> = [
    ["TGG", "pattern1"],
    ["GTT", "pattern1"],
    ["TTT", "pattern2"],
    ["GGG", "pattern2"],
    ["TGT", "pattern3"],
    ["GTG", "pattern3"],
    ["GGT", "pattern4"],
    ["TTG", "pattern4"],
    ["TTTT", "pattern5"],
    ["GGGG", "pattern5"],
  ];

  for (const [pattern, expectedKind] of cases) {
    const match = findH1PatternMatchesForTarget("GBPUSD", barsForPattern(pattern, 6), 6)
      .find((candidate) => candidate.slotHour === 6);
    assert.ok(match, pattern);
    assert.deepEqual(
      [match.pattern.join(""), match.patternKind, match.lookbackPattern, match.lookbackAction, match.tradeAllowed],
      [pattern, expectedKind, null, "none", true],
    );
  }
});

test("Pattern 5 has longest-match precedence for every run of four or more", () => {
  for (const sequence of ["TTTT", "TTTTT", "GGGG", "GGGGGG"]) {
    const match = findH1PatternMatchesForTarget("AUDUSD", barsFromOldest(sequence, 6 - sequence.length), 6)
      .find((candidate) => candidate.slotHour === 6);
    assert.ok(match);
    assert.equal(match.patternKind, "pattern5");
    assert.equal(match.pattern.length, 4);
  }
});

test("removed pattern actions cannot block or mutate any scanner row", () => {
  const dayBars = barsFromOldest("TGTGGTTGTGGTTGTT", 0);
  for (const base of H1_TARGET_BASES) {
    for (const match of findH1PatternMatchesForTarget(base, dayBars, 16)) {
      assert.deepEqual([match.lookbackPattern, match.lookbackAction, match.tradeAllowed], [null, "none", true]);
    }
  }
});

test("XAUUSD no longer has an H4 inheritance exception", () => {
  assert.equal(baseSymbolForTargetSlot("XAUUSD", 3), "GBPUSD");
  assert.equal(baseSymbolForTargetSlot("XAUUSD", 6), "GBPUSD");
  assert.equal(findH1PatternMatchesForTarget("XAUUSD", barsForPattern("TGG", 3), 4).some((match) => match.slotHour === 4), false);
});

test("only Thursday and Friday special cycles may invert post-signal", () => {
  for (const date of ["2026-08-17", "2026-08-18", "2026-08-19"]) {
    assert.deepEqual(postSignalDecision(date, 9), { inverted: false, rule: "none" });
  }
  assert.deepEqual(postSignalDecision("2026-07-02", 9), { inverted: true, rule: "thu-cycle" });
  assert.deepEqual(postSignalDecision("2026-08-21", 9), { inverted: true, rule: "fri-cycle" });
});

test("patterns classify only; calendar remains the sole post-base mutation", () => {
  const mondayMatch = findH1PatternMatchesForTarget("GBPUSD", barsForPattern("TGT", 6, "2026-08-17"), 6)
    .find((match) => match.slotHour === 6)!;
  const monday = buildStoredAlert({
    base: "GBPUSD",
    brokerSymbol: "GBPUSD",
    scannerBase: "GBPUSD",
    scannerSymbol: "GBPUSD",
    match: mondayMatch,
    baseSymbol: "XAUUSD",
    baseBar: barsFromOldest("T", 5, "2026-08-17")[0],
  });
  assert.deepEqual(
    [monday.patternKind, monday.baseH1Signal, monday.postSignalRule, monday.symbolH1Signal],
    ["pattern3", "BUY", "none", "BUY"],
  );

  const fridayMatch = findH1PatternMatchesForTarget("GBPUSD", barsForPattern("TGT", 6, "2026-08-21"), 6)
    .find((match) => match.slotHour === 6)!;
  const friday = buildStoredAlert({
    base: "GBPUSD",
    brokerSymbol: "GBPUSD",
    scannerBase: "GBPUSD",
    scannerSymbol: "GBPUSD",
    match: fridayMatch,
    baseSymbol: "XAUUSD",
    baseBar: barsFromOldest("T", 5, "2026-08-21")[0],
  });
  assert.deepEqual(
    [friday.patternKind, friday.baseH1Signal, friday.postSignalRule, friday.symbolH1Signal],
    ["pattern3", "BUY", "fri-cycle", "SELL"],
  );
});

test("target scanner and base mappings stay explicit across all six slots", () => {
  const expected = {
    XAUUSD: ["XAUUSD", "GBPUSD"],
    GBPUSD: ["GBPUSD", "XAUUSD"],
    AUDUSD: ["AUDUSD", "XAUUSD"],
    USDCAD: ["USDCAD", "GBPUSD"],
    USDJPY: ["USDJPY", "USDCAD"],
  } as const;
  for (const base of H1_TARGET_BASES) {
    assert.deepEqual([scannerBaseForTarget(base), baseSymbolForTarget(base)], expected[base]);
    for (const slotHour of H1_SCAN_HOURS) assert.equal(baseSymbolForTargetSlot(base, slotHour), expected[base][1]);
  }
});

test("state v45 round-trips into a rule-39 public feed with the fixed grid", () => {
  const match = findH1PatternMatchesForTarget("XAUUSD", barsForPattern("TGG", 6), 6)
    .find((candidate) => candidate.slotHour === 6)!;
  const alert = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    scannerBase: "XAUUSD",
    scannerSymbol: "XAUUSD",
    match,
    baseSymbol: "GBPUSD",
    baseBar: barsFromOldest("T", 5)[0],
  });
  const state = emptyCloudState();
  state.days["2026-08-17"] = { symbols: { XAUUSD: { alerts: [alert], blockedSlots: [] } } };

  const parsed = parseCloudState(JSON.stringify(state));
  const feed = buildPublicFeed(parsed, "2026-08-17T17:00:00.000Z");
  assert.deepEqual([parsed.version, feed.signalRuleVersion, feed.hours], [45, 39, [3, 6, 9, 12, 14, 16]]);
  assert.deepEqual(
    [feed.days["2026-08-17"].symbols.XAUUSD?.alerts[0]?.patternKind, feed.days["2026-08-17"].symbols.XAUUSD?.alerts[0]?.tradeAllowed],
    ["pattern1", true],
  );
  assert.throws(() => parseCloudState({ ...state, version: 44 }), /schema/);
});
