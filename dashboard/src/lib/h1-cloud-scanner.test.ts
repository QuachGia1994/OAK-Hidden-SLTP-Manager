import assert from "node:assert/strict";
import test from "node:test";

import {
  H1_CLOUD_PROFILE,
  H1_CLOUD_STATE_KEY,
  H1_CLOUD_STATE_VERSION,
  H1_LEGACY_CLOUD_STATE_KEYS,
  H1_PUBLIC_SCHEMA,
  H1_SCAN_END_HOUR,
  H1_SCAN_HOURS,
  H1_SIGNAL_END_HOUR,
  H1_SIGNAL_RULE_VERSION,
  H1_TARGET_BASES,
  buildPublicFeed,
  emptyCloudState,
  ensureSymbolDay,
  evaluateLocalH1PatternsForTarget,
  h1BlockSignalPlan,
  highlightedH1BlockHoursForBrokerDate,
  h1TargetBaseFromSymbol,
  h1TpRollMilestonesForBrokerDate,
  mergeH1CloudStateHistory,
  parseCloudState,
  parsePublicFeedCloudState,
  scheduledSignalSlotForBrokerHour,
  scheduledSignalSlotForVietnamWall,
  targetsForBlockHour,
  type H1LocalMarketSnapshot,
} from "./h1-cloud-scanner.ts";
import { icMarketsBrokerWallEpochMs } from "./h1-broker-date.ts";
import type { H1M15Bar } from "./h1-local-patterns.ts";

function candle(date: string, hour: number, minute: number, direction: "T" | "G", seed = 100): H1M15Bar {
  const open = seed;
  const close = direction === "T" ? open + 1 : open - 1;
  return { brokerDate: date, hour, minute, direction, open, high: Math.max(open, close) + 0.2, low: Math.min(open, close) - 0.2, close };
}

function patternBars(date: string, slotHour: number, sequence = "TTGTTT", family: "ALT" | "SAME" = "ALT"): H1M15Bar[] {
  const shift = slotHour - 3;
  const rows: Array<[number, number, "T" | "G"]> = [];
  if (family === "ALT") {
    rows.push([2 + shift, 45, "T"], [2 + shift, 30, "G"]);
    const times = [[2, 15], [2, 0], [1, 45], [1, 30], [1, 15], [1, 0]] as const;
    [...sequence].forEach((direction, index) => rows.push([times[index][0] + shift, times[index][1], direction as "T" | "G"]));
  } else {
    rows.push([2 + shift, 45, "T"]);
    const times = [[2, 30], [2, 15], [2, 0], [1, 45], [1, 30], [1, 15]] as const;
    [...sequence].forEach((direction, index) => rows.push([times[index][0] + shift, times[index][1], direction as "T" | "G"]));
  }
  return rows.map(([hour, minute, direction], index) => candle(date, hour, minute, direction, 200 + index));
}

function source(displayName: string) {
  return { displayName, bars: [] as H1M15Bar[], h1Bars: [] as H1M15Bar[] };
}

function market(date: string, slotHour: number, sequence = "TTGTTT"): H1LocalMarketSnapshot {
  const snapshot = {
    XAUUSD: source("XAUUSD"),
    GBPUSD: source("GBPUSD"),
    GBPAUD: source("GBPAUD"),
  } as H1LocalMarketSnapshot;
  snapshot.XAUUSD.bars = patternBars(date, slotHour, sequence);
  return snapshot;
}

function setM15(snapshot: H1LocalMarketSnapshot, symbol: keyof H1LocalMarketSnapshot, date: string, hour: number, minute: number, direction: "T" | "G") {
  snapshot[symbol].bars = [
    ...snapshot[symbol].bars.filter((bar) => !(bar.brokerDate === date && bar.hour === hour && bar.minute === minute)),
    candle(date, hour, minute, direction, 500 + hour + minute / 100),
  ];
}

function setH1(snapshot: H1LocalMarketSnapshot, symbol: "GBPUSD" | "GBPAUD", date: string, hour: number, direction: "T" | "G") {
  const sourceSnapshot = snapshot[symbol as keyof H1LocalMarketSnapshot];
  sourceSnapshot.h1Bars = [
    ...sourceSnapshot.h1Bars.filter((bar) => !(bar.brokerDate === date && bar.hour === hour)),
    candle(date, hour, 0, direction, 700 + hour),
  ];
}

function alertFor(
  snapshot: H1LocalMarketSnapshot,
  date: string,
  slotHour: number,
) {
  return evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [3, 6, 9, 12], slotHour)
    .find((alert) => alert.slotHour === slotHour);
}

test("rule v99 keeps schema/state stable, exposes only GBPAUD public signal and removes H14", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 56);
  assert.equal(H1_PUBLIC_SCHEMA, 18);
  assert.equal(H1_SIGNAL_RULE_VERSION, 99);
  assert.equal(H1_CLOUD_PROFILE, "MT5 ICMarkets Local");
  assert.equal(H1_SCAN_END_HOUR, 12);
  assert.equal(H1_SIGNAL_END_HOUR, 12);
  assert.deepEqual(H1_SCAN_HOURS, [3, 6, 9, 12]);
  assert.deepEqual(H1_TARGET_BASES, ["XAUUSD"]);
  assert.deepEqual(targetsForBlockHour(12), ["XAUUSD"]);
  assert.deepEqual(targetsForBlockHour(14), []);
});

test("every entry uses the exact GBPUSD M15 candle at entry minus 15 minutes", () => {
  assert.deepEqual(h1BlockSignalPlan(3, 4), { baseSymbol: "GBPUSD", baseHour: 3, baseMinute: 45, inverted: true, rule: "block-base-invert" });
  assert.deepEqual(h1BlockSignalPlan(3, 5), { baseSymbol: "GBPUSD", baseHour: 4, baseMinute: 45, inverted: true, rule: "block-base-invert" });
  assert.deepEqual(h1BlockSignalPlan(6, 7), { baseSymbol: "GBPUSD", baseHour: 6, baseMinute: 45, inverted: false, rule: "block-base-keep" });
  assert.deepEqual(h1BlockSignalPlan(6, 8), { baseSymbol: "GBPUSD", baseHour: 7, baseMinute: 45, inverted: false, rule: "block-base-keep" });
});

test("active blocks keep their GBPUSD M15 base at entry minus 15 minutes", () => {
  const date = "2026-09-09";
  const cases = [
    { slot: 3, entry: 4, direction: "T" as const, expected: "SELL" },
    { slot: 6, entry: 7, direction: "T" as const, expected: "BUY" },
    { slot: 9, entry: 10, direction: "T" as const, expected: "BUY" },
    { slot: 12, entry: 13, direction: "T" as const, expected: "SELL" },
  ];
  const snapshot = market(date, 3, "TTGTTT");
  for (const item of cases) {
    const baseHour = item.entry - 1;
    setM15(snapshot, "GBPUSD", date, baseHour, 45, item.direction);
    const alert = alertFor(snapshot, date, item.slot);
    assert.deepEqual(
      [alert?.entryHour, alert?.baseSymbol, alert?.baseHour, alert?.baseMinute, alert?.baseH1Signal, alert?.postSignalInverted, alert?.symbolH1Signal, alert?.signalBaseBar?.brokerTime],
      [item.entry, "GBPUSD", baseHour, 45, item.direction === "T" ? "BUY" : "SELL", item.slot === 3 || item.slot === 12, item.expected, `${String(baseHour).padStart(2, "0")}:45`],
    );
  }
});

test("block presentation highlights are disabled on every broker weekday", () => {
  for (const date of ["2026-09-07", "2026-09-08", "2026-09-09", "2026-09-10", "2026-09-11", "2026-09-12", "2026-09-13"]) {
    assert.deepEqual(highlightedH1BlockHoursForBrokerDate(date), []);
  }
});

test("SW entry H5 uses GBPUSD 04:45 and H3 inverts that raw base", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 3, "TGGTTT"); // SW => entry H5 => base 04:45
  setM15(snapshot, "GBPUSD", date, 3, 45, "G"); // decoy BT-style base
  setM15(snapshot, "GBPUSD", date, 4, 45, "T");
  const alert = alertFor(snapshot, date, 3);
  assert.deepEqual([alert?.entryHour, alert?.baseHour, alert?.baseMinute, alert?.baseH1Signal, alert?.symbolH1Signal], [5, 4, 45, "BUY", "SELL"]);
});

test("H14 is retired as a block while H12 may still enter at H14", () => {
  const date = "2026-09-09";
  assert.equal(scheduledSignalSlotForBrokerHour("XAUUSD", date, 14), 12);
  assert.deepEqual(targetsForBlockHour(14), []);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 18, 4), 9);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 18, 5), 12);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 20, 4), 12);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 20, 5), null);
  assert.equal(h1TargetBaseFromSymbol("XAUUSD.a"), "XAUUSD");
  assert.equal(h1TargetBaseFromSymbol("GOLD"), "XAUUSD");
  assert.equal(h1TargetBaseFromSymbol("GBPUSD"), null);
  assert.equal(h1TargetBaseFromSymbol("GBPAUD"), null);
});

test("only H3 determines entry delta +1 and cascades H4/H7/H10/H13", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 3, "TTGTTT");
  setM15(snapshot, "GBPUSD", date, 3, 45, "T");
  setM15(snapshot, "GBPUSD", date, 6, 45, "T");
  setM15(snapshot, "GBPUSD", date, 9, 45, "T");
  setM15(snapshot, "GBPUSD", date, 12, 45, "T");
  for (const hour of [3, 6, 9, 12]) setH1(snapshot, "GBPAUD", date, hour, "T");

  const alerts = evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [3, 6, 9, 12], 12);
  assert.deepEqual(alerts.map((alert) => alert.entryHour), [4, 7, 10, 13]);
  assert.deepEqual(alerts.map((alert) => alert.ownH1Signals?.GBPAUD?.baseHour), [3, 6, 9, 12]);
  assert.deepEqual(alerts.map((alert) => alert.ownH1Signals?.GBPAUD?.symbolH1Signal), ["BUY", "BUY", "BUY", "BUY"]);
  assert.deepEqual(alerts.map((alert) => alert.ownH1Signals?.GBPAUD?.postSignalInverted), [false, false, false, false]);
});

test("only H3 determines entry delta +2 and cascades H5/H8/H11/H14", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 3, "TGGTTT");
  setM15(snapshot, "GBPUSD", date, 4, 45, "T");
  setM15(snapshot, "GBPUSD", date, 7, 45, "T");
  setM15(snapshot, "GBPUSD", date, 10, 45, "T");
  setM15(snapshot, "GBPUSD", date, 13, 45, "T");
  for (const hour of [4, 7, 10, 13]) setH1(snapshot, "GBPAUD", date, hour, "G");

  const alerts = evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [3, 6, 9, 12], 12);
  assert.deepEqual(alerts.map((alert) => alert.entryHour), [5, 8, 11, 14]);
  assert.deepEqual(alerts.map((alert) => alert.ownH1Signals?.GBPAUD?.baseHour), [4, 7, 10, 13]);
  assert.deepEqual(alerts.map((alert) => alert.ownH1Signals?.GBPAUD?.baseH1Signal), ["SELL", "SELL", "SELL", "SELL"]);
  assert.deepEqual(alerts.map((alert) => alert.ownH1Signals?.GBPAUD?.symbolH1Signal), ["SELL", "SELL", "SELL", "SELL"]);
  assert.deepEqual(alerts.map((alert) => alert.ownH1Signals?.GBPAUD?.postSignalInverted), [false, false, false, false]);
});

test("cloud state v56 round-trips v99 cascaded entry evidence", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 3, "TTGTTT");
  setM15(snapshot, "GBPUSD", date, 12, 45, "T");
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push(...evaluateLocalH1PatternsForTarget(
    "XAUUSD", date, snapshot, [3, 6, 9, 12], 12,
  ));
  const stored = parseCloudState(JSON.stringify(state)).days[date].symbols.XAUUSD?.alerts.find((alert) => alert.slotHour === 12);
  assert.deepEqual([stored?.entryHour, stored?.baseSymbol, stored?.baseHour, stored?.baseMinute, stored?.baseH1Signal, stored?.symbolH1Signal, stored?.postSignalRule], [13, "GBPUSD", 12, 45, "BUY", "SELL", "block-base-invert"]);
  assert.equal(stored?.signalBaseBar?.brokerTime, "12:45");
});

test("public feed v99 exposes cascaded entry hours and raw GBPAUD H1 signals", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 3, "TTGTTT");
  for (const hour of [3, 6, 9, 12]) setM15(snapshot, "GBPUSD", date, hour, 45, "T");
  for (const hour of [3, 6, 9, 12]) setH1(snapshot, "GBPAUD", date, hour, hour === 9 ? "G" : "T");
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push(...evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [3, 6, 9, 12], 12));
  const feed = buildPublicFeed(state, "2026-09-09T01:00:00.000Z");
  assert.deepEqual([feed.schemaVersion, feed.signalRuleVersion, feed.hours, feed.symbols], [18, 99, [3, 6, 9, 12], ["GBPAUD"]]);
  assert.equal("XAUUSD" in feed.days[date].symbols, false);
  assert.equal("GBPUSD" in feed.days[date].symbols, false);
  const rows = feed.days[date].symbols.GBPAUD?.alerts ?? [];
  assert.deepEqual(rows.map((row) => row.entryHour), [4, 7, 10, 13]);
  assert.deepEqual(rows.map((row) => row.baseHour), [3, 6, 9, 12]);
  assert.deepEqual(rows.map((row) => row.signal), ["BUY", "BUY", "SELL", "BUY"]);
  assert.ok(rows.every((row) => row.postSignalInverted === false));
});

test("GBPAUD always uses entry minus one H1 with raw direction, including H12 entry H14", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 3, "TGGTTT");
  for (const [hour, direction] of [[4, "T"], [7, "G"], [10, "T"], [13, "G"]] as const) setH1(snapshot, "GBPAUD", date, hour, direction);
  const alerts = evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [3, 6, 9, 12], 12);
  assert.deepEqual(alerts.map((alert) => [alert.slotHour, alert.entryHour, alert.ownH1Signals?.GBPAUD?.baseHour, alert.ownH1Signals?.GBPAUD?.symbolH1Signal]), [
    [3, 5, 4, "BUY"],
    [6, 8, 7, "SELL"],
    [9, 11, 10, "BUY"],
    [12, 14, 13, "SELL"],
  ]);
});

test("GBPAUD signal fails closed when its exact entry-minus-one H1 candle is missing", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 3, "TGGTTT"); // SW => entry H5 => exact base H4
  setH1(snapshot, "GBPAUD", date, 3, "T"); // decoy
  const alert = alertFor(snapshot, date, 3);
  const own = alert?.ownH1Signals?.GBPAUD;
  assert.equal(alert?.entryHour, 5);
  assert.equal(own?.baseHour, 4);
  assert.equal(own?.symbolH1Signal, null);
});

test("v99 TP milestones expose only active blocks while H12 may due at H14", () => {
  const date = "2026-09-10";
  const snapshot = market(date, 3, "TGGTTT");
  for (const hour of [4, 7, 10, 13]) setM15(snapshot, "GBPUSD", date, hour, 45, "T");
  for (const hour of [4, 7, 10, 13]) setH1(snapshot, "GBPAUD", date, hour, "T");
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push(...evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [3, 6, 9, 12], 12));
  const rows = h1TpRollMilestonesForBrokerDate(state, date);
  assert.deepEqual(rows.filter((row) => row.symbol === "GBPAUD").map((row) => [row.blockHour, row.entryHour]), [[3, 5], [6, 8], [9, 11], [12, 14]]);
  assert.equal(rows.some((row) => String(row.symbol) === "GBPAUD" && row.blockHour === 14), false);
  assert.equal(icMarketsBrokerWallEpochMs("2026-01-15", 7), Date.parse("2026-01-15T05:00:00.000Z"));
  assert.equal(icMarketsBrokerWallEpochMs("2026-09-10", 7), Date.parse("2026-09-10T04:00:00.000Z"));
});

test("v98 migration drops retired stored FX/H16 rows and rejects stale v97 public feeds", () => {
  const date = "2026-09-09";
  const stale = emptyCloudState();
  stale.days[date] = {
    symbols: {
      XAUUSD: { alerts: [{
        slotHour: 3, symbol: "XAUUSD", profile: H1_CLOUD_PROFILE, baseSymbol: "XAUUSD",
        baseH1Signal: "BUY", baseHour: 1, baseMinute: 45, baseDirection: "T", symbolH1Signal: "BUY",
        scheduledSignal: null, postSignalInverted: false, postSignalRule: "h3-prev-h4-keep", entryHour: 4,
        patternGroup: "BT", patternFamily: "ALT", pattern: "TTG", scannerSource: "XAUUSD", inversionBadge: false, sampleBars: [], signalBaseBar: null,
      }] },
      GBPUSD: { alerts: [] },
      AUDUSD: { alerts: [] },
      USDCAD: { alerts: [] },
      USDJPY: { alerts: [] },
    } as never,
  };
  const parsed = parseCloudState(JSON.stringify(stale));
  assert.deepEqual(parsed.days[date].symbols.XAUUSD?.alerts, []);
  assert.deepEqual(Object.keys(parsed.days[date].symbols), ["XAUUSD"]);
  assert.equal(parsePublicFeedCloudState({ ...buildPublicFeed(emptyCloudState()), signalRuleVersion: 97 }), null);
});

test("rule bumps keep H1 history on schema-stable state key and merge dates", () => {
  assert.equal(H1_CLOUD_STATE_KEY, `robot-sltp:cloud:h1-scanner:state:s${H1_CLOUD_STATE_VERSION}`);
  assert.deepEqual(H1_LEGACY_CLOUD_STATE_KEYS, ["robot-sltp:cloud:h1-scanner:state:v73", "robot-sltp:cloud:h1-scanner:state:v72"]);
  const history = emptyCloudState();
  history.days["2026-09-08"] = { symbols: { XAUUSD: { alerts: [] } } };
  const current = emptyCloudState();
  current.days["2026-09-09"] = { symbols: { XAUUSD: { alerts: [] } } };
  assert.deepEqual(Object.keys(mergeH1CloudStateHistory(history, current).days).sort(), ["2026-09-08", "2026-09-09"]);
});
