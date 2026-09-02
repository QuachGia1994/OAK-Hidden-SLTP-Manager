import assert from "node:assert/strict";
import test from "node:test";

import {
  H1_CLOUD_PROFILE,
  H1_CLOUD_STATE_VERSION,
  H1_PUBLIC_SCHEMA,
  H1_SCAN_HOURS,
  H1_SIGNAL_RULE_VERSION,
  H1_TARGET_BASES,
  buildPublicFeed,
  emptyCloudState,
  ensureSymbolDay,
  evaluateLocalH1PatternsForTarget,
  h1TargetBaseFromSymbol,
  parseCloudState,
  parsePublicFeedCloudState,
  scheduledSignalSlotForVietnamWall,
  targetsForBlockHour,
  type H1LocalMarketSnapshot,
} from "./h1-cloud-scanner.ts";
import type { H1M15Bar } from "./h1-local-patterns.ts";

function bars(date: string, sequence: string, family: "ALT" | "SAME"): H1M15Bar[] {
  const rows: Array<[number, number, "T" | "G"]> = [];
  if (family === "ALT") {
    rows.push([2, 45, "T"], [2, 30, "G"]);
    const times = [[2, 15], [2, 0], [1, 45], [1, 30], [1, 15], [1, 0]] as const;
    [...sequence].forEach((direction, index) => rows.push([times[index][0], times[index][1], direction as "T" | "G"]));
  } else {
    rows.push([2, 45, "T"]);
    const times = [[2, 30], [2, 15], [2, 0], [1, 45], [1, 30], [1, 15]] as const;
    [...sequence].forEach((direction, index) => rows.push([times[index][0], times[index][1], direction as "T" | "G"]));
  }
  return rows.map(([hour, minute, direction]) => ({ brokerDate: date, hour, minute, direction }));
}

function market(date: string, sequence = "TGTGTG", family: "ALT" | "SAME" = "ALT"): H1LocalMarketSnapshot {
  const sourceBars = bars(date, sequence, family);
  return {
    XAUUSD: { displayName: "XAUUSD", bars: sourceBars.filter((row) => !(family === "ALT" && row.hour === 1 && row.minute === 0)) },
    AUDUSD: { displayName: "AUDUSD", bars: sourceBars },
    USDJPY: { displayName: "USDJPY", bars: sourceBars },
    GBPUSD: { displayName: "GBPUSD", bars: sourceBars },
  };
}

test("rule v59 uses local MT5 ICMarkets, schema 18 and six blocks", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 56);
  assert.equal(H1_PUBLIC_SCHEMA, 18);
  assert.equal(H1_SIGNAL_RULE_VERSION, 59);
  assert.equal(H1_CLOUD_PROFILE, "MT5 ICMarkets Local");
  assert.deepEqual(H1_SCAN_HOURS, [3, 6, 9, 12, 14, 16]);
  assert.deepEqual(H1_TARGET_BASES, ["XAUUSD", "GBPUSD", "GBPAUD", "GBPCAD", "GBPJPY"]);
});

test("H3/H6 omit GBPUSD while later blocks expose all five rows", () => {
  assert.deepEqual(targetsForBlockHour(3), ["XAUUSD", "GBPAUD", "GBPCAD", "GBPJPY"]);
  assert.deepEqual(targetsForBlockHour(6), ["XAUUSD", "GBPAUD", "GBPCAD", "GBPJPY"]);
  for (const hour of [9, 12, 14, 16]) assert.deepEqual(targetsForBlockHour(hour), [...H1_TARGET_BASES]);
  assert.deepEqual(targetsForBlockHour(4), []);
});

test("local pattern evaluation writes entry hour, pattern group, source and weekday inversion", () => {
  const date = "2026-09-02"; // Wednesday
  const alerts = evaluateLocalH1PatternsForTarget("GBPAUD", date, market(date, "TGTGTG", "ALT"), [3], 3);
  assert.equal(alerts.length, 1);
  assert.deepEqual(
    [alerts[0].slotHour, alerts[0].entryHour, alerts[0].patternGroup, alerts[0].scannerSource, alerts[0].inversionBadge],
    [3, 5, "SW", "AUDUSD", true],
  );
  assert.equal(alerts[0].symbolH1Signal, null);
});

test("GBPCAD derives H3 from AUDUSD and later blocks from USDJPY", () => {
  const date = "2026-09-02";
  const snapshot = market(date, "TGGTTT", "ALT");
  const h3 = evaluateLocalH1PatternsForTarget("GBPCAD", date, snapshot, [3], 3)[0];
  assert.equal(h3?.scannerSource, "AUDUSD");

  // Shift the same six-bar shape from H3 to H9 for the USDJPY source.
  snapshot.USDJPY.bars = snapshot.USDJPY.bars.map((row) => ({ ...row, hour: row.hour + 6 }));
  const h9 = evaluateLocalH1PatternsForTarget("GBPCAD", date, snapshot, [9], 9)[0];
  assert.equal(h9?.scannerSource, "USDJPY");
});

test("Monday local evaluation leaves every FX row blank", () => {
  const monday = "2026-09-07";
  const snapshot = market(monday, "TGGTTT", "ALT");
  for (const base of ["GBPUSD", "GBPAUD", "GBPCAD", "GBPJPY"] as const) {
    assert.deepEqual(evaluateLocalH1PatternsForTarget(base, monday, snapshot, H1_SCAN_HOURS, 16), []);
  }
});

test("timed Telegram mapping follows the reopened six block set", () => {
  const date = "2026-09-02";
  assert.equal(h1TargetBaseFromSymbol("xauusd+"), "XAUUSD");
  assert.equal(h1TargetBaseFromSymbol("GBPCAD.a"), "GBPCAD");
  assert.equal(h1TargetBaseFromSymbol("EURUSD"), null);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 9, 5), 3);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 10, 5), 3);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 12, 5), 6);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPUSD", date, 9, 5), null);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPUSD", date, 12, 5), null);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPUSD", date, 15, 5), 9);
});

test("cloud state v56 round-trips a local pattern alert", () => {
  const date = "2026-09-02";
  const state = emptyCloudState();
  const alert = evaluateLocalH1PatternsForTarget("GBPAUD", date, market(date, "TGGTTT", "ALT"), [3], 3)[0];
  ensureSymbolDay(state, date, "GBPAUD").symbol.alerts.push(alert);
  const parsed = parseCloudState(JSON.stringify(state));
  const stored = parsed.days[date].symbols.GBPAUD?.alerts[0];
  assert.equal(stored?.entryHour, 5);
  assert.equal(stored?.patternGroup, "SW");
  assert.equal(stored?.scannerSource, "AUDUSD");
  assert.equal(stored?.inversionBadge, true);
  assert.throws(() => parseCloudState({ version: 55, days: {} }), /schema/i);
});

test("public feed schema 18 exposes entry time and inversion badge and can seed state", () => {
  const date = "2026-09-02";
  const state = emptyCloudState();
  const alert = evaluateLocalH1PatternsForTarget("GBPAUD", date, market(date, "TTGTTT", "ALT"), [3], 3)[0];
  ensureSymbolDay(state, date, "GBPAUD").symbol.alerts.push(alert);
  const feed = buildPublicFeed(state, "2026-09-02T01:00:00.000Z");
  assert.deepEqual([feed.schemaVersion, feed.signalRuleVersion, feed.hours], [18, 59, [3, 6, 9, 12, 14, 16]]);
  const row = feed.days[date].symbols.GBPAUD?.alerts[0];
  assert.deepEqual([row?.entryHour, row?.patternGroup, row?.scannerSource, row?.inversionBadge], [4, "BT", "AUDUSD", true]);
  const seeded = parsePublicFeedCloudState(feed);
  assert.equal(seeded?.days[date].symbols.GBPAUD?.alerts[0].entryHour, 4);
});
