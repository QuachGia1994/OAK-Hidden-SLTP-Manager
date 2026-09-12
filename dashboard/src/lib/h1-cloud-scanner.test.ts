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
  type H1StoredAlert,
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
  const snapshot: H1LocalMarketSnapshot = {
    XAUUSD: source("XAUUSD"),
    GBPUSD: source("GBPUSD"),
  };
  snapshot.XAUUSD.bars = patternBars(date, slotHour, sequence);
  return snapshot;
}

function setM15(snapshot: H1LocalMarketSnapshot, symbol: keyof H1LocalMarketSnapshot, date: string, hour: number, minute: number, direction: "T" | "G") {
  snapshot[symbol].bars = [
    ...snapshot[symbol].bars.filter((bar) => !(bar.brokerDate === date && bar.hour === hour && bar.minute === minute)),
    candle(date, hour, minute, direction, 500 + hour + minute / 100),
  ];
}

function alertFor(snapshot: H1LocalMarketSnapshot, date: string, slotHour: number) {
  return evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [slotHour], slotHour)[0];
}

function storedXauAlert(slotHour: number, entryDelta: 1 | 2, signal: "BUY" | "SELL"): H1StoredAlert {
  const entryHour = slotHour + entryDelta;
  const plan = h1BlockSignalPlan(slotHour, entryHour);
  assert.ok(plan);
  const baseSignal = plan.inverted ? (signal === "BUY" ? "SELL" : "BUY") : signal;
  return {
    slotHour,
    symbol: "XAUUSD",
    profile: H1_CLOUD_PROFILE,
    baseSymbol: plan.baseSymbol,
    baseH1Signal: baseSignal,
    baseHour: plan.baseHour,
    baseMinute: plan.baseMinute,
    baseDirection: baseSignal === "BUY" ? "T" : "G",
    symbolH1Signal: signal,
    scheduledSignal: null,
    postSignalInverted: plan.inverted,
    postSignalRule: plan.rule,
    entryHour,
    patternGroup: entryDelta === 1 ? "BT" : "SW",
    patternFamily: "ALT",
    pattern: entryDelta === 1 ? "TTG" : "TGG",
    scannerSource: "XAUUSD",
    inversionBadge: plan.inverted,
    sampleBars: [],
    signalBaseBar: null,
  };
}

test("rule v95 keeps schema/state stable, exposes three public signal rows and removes H16", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 56);
  assert.equal(H1_PUBLIC_SCHEMA, 18);
  assert.equal(H1_SIGNAL_RULE_VERSION, 95);
  assert.equal(H1_CLOUD_PROFILE, "MT5 ICMarkets Local");
  assert.equal(H1_SCAN_END_HOUR, 14);
  assert.equal(H1_SIGNAL_END_HOUR, 14);
  assert.deepEqual(H1_SCAN_HOURS, [3, 6, 9, 12, 14]);
  assert.deepEqual(H1_TARGET_BASES, ["XAUUSD"]);
  assert.deepEqual(targetsForBlockHour(14), ["XAUUSD"]);
  assert.deepEqual(targetsForBlockHour(16), []);
});

test("every entry uses the exact GBPUSD M15 candle at entry minus 15 minutes", () => {
  assert.deepEqual(h1BlockSignalPlan(3, 4), { baseSymbol: "GBPUSD", baseHour: 3, baseMinute: 45, inverted: true, rule: "block-base-invert" });
  assert.deepEqual(h1BlockSignalPlan(3, 5), { baseSymbol: "GBPUSD", baseHour: 4, baseMinute: 45, inverted: true, rule: "block-base-invert" });
  assert.deepEqual(h1BlockSignalPlan(6, 7), { baseSymbol: "GBPUSD", baseHour: 6, baseMinute: 45, inverted: false, rule: "block-base-keep" });
  assert.deepEqual(h1BlockSignalPlan(6, 8), { baseSymbol: "GBPUSD", baseHour: 7, baseMinute: 45, inverted: false, rule: "block-base-keep" });
});

test("all five blocks use GBPUSD M15 E-0:15 with the requested KEEP/INVERT policy", () => {
  const date = "2026-09-09";
  const cases = [
    { slot: 3, inverted: true, direction: "T" as const, expected: "SELL" },
    { slot: 6, inverted: false, direction: "T" as const, expected: "BUY" },
    { slot: 9, inverted: false, direction: "T" as const, expected: "BUY" },
    { slot: 12, inverted: true, direction: "T" as const, expected: "SELL" },
    { slot: 14, inverted: true, direction: "G" as const, expected: "BUY" },
  ];
  for (const item of cases) {
    const snapshot = market(date, item.slot, "TTGTTT"); // BT => entry block+1
    const baseHour = item.slot;
    setM15(snapshot, "GBPUSD", date, baseHour, 45, item.direction);
    const alert = alertFor(snapshot, date, item.slot);
    assert.deepEqual(
      [alert?.entryHour, alert?.baseSymbol, alert?.baseHour, alert?.baseMinute, alert?.baseH1Signal, alert?.postSignalInverted, alert?.symbolH1Signal, alert?.signalBaseBar?.brokerTime],
      [item.slot + 1, "GBPUSD", baseHour, 45, item.direction === "T" ? "BUY" : "SELL", item.inverted, item.expected, `${String(baseHour).padStart(2, "0")}:45`],
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

test("entry evidence survives while signal fails closed until the required GBPUSD M15 base exists", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 14, "TGGTTT"); // SW => H16, base GBPUSD 15:45
  const alert = alertFor(snapshot, date, 14);
  assert.deepEqual([alert?.entryHour, alert?.baseSymbol, alert?.baseHour, alert?.baseMinute, alert?.baseH1Signal, alert?.symbolH1Signal], [16, "GBPUSD", 15, 45, null, null]);
  assert.ok((alert?.sampleBars?.length || 0) > 0);
});

test("H16 is retired while Telegram appointment cutoff remains H14", () => {
  const date = "2026-09-09";
  assert.equal(scheduledSignalSlotForBrokerHour("XAUUSD", date, 16), 14);
  assert.deepEqual(targetsForBlockHour(16), []);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 22, 4), 14);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 22, 5), null);
  assert.equal(h1TargetBaseFromSymbol("XAUUSD.a"), "XAUUSD");
  assert.equal(h1TargetBaseFromSymbol("GOLD"), "XAUUSD");
  assert.equal(h1TargetBaseFromSymbol("GBPUSD"), null);
  assert.equal(h1TargetBaseFromSymbol("GBPAUD"), null);
});

test("cloud state v56 round-trips v95 XAU GBPUSD-M15 base evidence", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 12, "TTGTTT");
  setM15(snapshot, "GBPUSD", date, 12, 45, "T");
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push(alertFor(snapshot, date, 12));
  const stored = parseCloudState(JSON.stringify(state)).days[date].symbols.XAUUSD?.alerts[0];
  assert.deepEqual([stored?.baseSymbol, stored?.baseHour, stored?.baseMinute, stored?.baseH1Signal, stored?.symbolH1Signal, stored?.postSignalRule], ["GBPUSD", 12, 45, "BUY", "SELL", "block-base-invert"]);
  assert.equal(stored?.signalBaseBar?.brokerTime, "12:45");
});

test("public feed schema 18 exposes v95 XAUUSD + GBPUSD + GBPAUD rows", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 14, "TTGTTT");
  setM15(snapshot, "GBPUSD", date, 14, 45, "G");
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push(alertFor(snapshot, date, 14));
  const feed = buildPublicFeed(state, "2026-09-09T01:00:00.000Z");
  assert.deepEqual([feed.schemaVersion, feed.signalRuleVersion, feed.hours, feed.symbols], [18, 95, [3, 6, 9, 12, 14], ["XAUUSD", "GBPUSD", "GBPAUD"]]);
  const row = feed.days[date].symbols.XAUUSD?.alerts[0];
  assert.deepEqual([row?.baseSymbol, row?.baseHour, row?.baseMinute, row?.baseSignal, row?.signal, row?.postSignalRule, row?.postSignalInverted], ["GBPUSD", 14, 45, "SELL", "BUY", "block-base-invert", true]);
  const seeded = parsePublicFeedCloudState(feed);
  const seededRow = seeded?.days[date].symbols.XAUUSD?.alerts[0];
  assert.deepEqual([seededRow?.baseSymbol, seededRow?.baseH1Signal, seededRow?.symbolH1Signal], ["GBPUSD", "SELL", "BUY"]);
});

test("GBPUSD derived row follows the previous block entry-delta routing rule", () => {
  const date = "2026-09-09";
  const state = emptyCloudState();
  const alerts = [
    storedXauAlert(3, 2, "SELL"),
    storedXauAlert(6, 1, "BUY"),
    storedXauAlert(9, 2, "SELL"),
    storedXauAlert(12, 1, "BUY"),
    storedXauAlert(14, 1, "SELL"),
  ];
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push(...alerts);
  const rows = buildPublicFeed(state).days[date].symbols.GBPUSD?.alerts ?? [];
  assert.deepEqual(rows.map((row) => [row.slotHour, row.signal, row.baseHour, row.postSignalRule]), [
    [3, "SELL", 3, "xau-same-block-keep"],
    [6, "SELL", 3, "xau-previous-block-keep"],
    [9, "SELL", 9, "xau-same-block-keep"],
    [12, "SELL", 9, "xau-previous-block-keep"],
    [14, "SELL", 14, "xau-same-block-keep"],
  ]);
});

test("v95 TP milestones use each block's shared XAU Entry time and IC Markets DST-aware broker wall clock", () => {
  const date = "2026-09-10";
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push(
    storedXauAlert(3, 2, "BUY"),
    storedXauAlert(6, 1, "SELL"),
    storedXauAlert(9, 1, "BUY"),
    storedXauAlert(12, 1, "SELL"),
    storedXauAlert(14, 1, "BUY"),
  );
  const rows = h1TpRollMilestonesForBrokerDate(state, date);
  const gbpUsdH6 = rows.find((row) => row.symbol === "GBPUSD" && row.blockHour === 6);
  const gbpAudH6 = rows.find((row) => row.symbol === "GBPAUD" && row.blockHour === 6);
  assert.deepEqual([gbpUsdH6?.entryHour, gbpAudH6?.entryHour], [7, 7]);
  assert.equal(gbpUsdH6?.side, "BUY"); // H3 delta=2 routes the H6 GBPUSD signal from XAU H3, but due time stays H6 Entry H7.
  assert.equal(gbpUsdH6?.dueAt, Date.parse("2026-09-10T04:00:00.000Z"));
  assert.equal(gbpAudH6?.dueAt, Date.parse("2026-09-10T04:00:00.000Z"));
  assert.equal(rows.some((row) => row.symbol === "GBPAUD" && row.blockHour === 14), false);
  assert.equal(icMarketsBrokerWallEpochMs("2026-01-15", 7), Date.parse("2026-01-15T05:00:00.000Z"));
  assert.equal(icMarketsBrokerWallEpochMs("2026-09-10", 7), Date.parse("2026-09-10T04:00:00.000Z"));
});

test("GBPAUD derived row applies the weekday/block inversion matrix and leaves H14 blank", () => {
  const cases = [
    { date: "2026-09-07", expected: [[3, "SELL"], [6, "SELL"], [9, "BUY"], [12, "BUY"]] },
    { date: "2026-09-09", expected: [[3, "BUY"], [6, "BUY"], [9, "BUY"], [12, "BUY"]] },
    { date: "2026-09-10", expected: [[3, "SELL"], [6, "SELL"], [9, "SELL"], [12, "SELL"]] },
    { date: "2026-09-11", expected: [[3, "BUY"], [6, "BUY"], [9, "SELL"], [12, "SELL"]] },
  ] as const;
  for (const item of cases) {
    const state = emptyCloudState();
    ensureSymbolDay(state, item.date, "XAUUSD").symbol.alerts.push(
      storedXauAlert(3, 1, "BUY"),
      storedXauAlert(6, 1, "BUY"),
      storedXauAlert(9, 1, "BUY"),
      storedXauAlert(12, 1, "BUY"),
      storedXauAlert(14, 1, "BUY"),
    );
    const rows = buildPublicFeed(state).days[item.date].symbols.GBPAUD?.alerts ?? [];
    assert.deepEqual(rows.map((row) => [row.slotHour, row.signal]), item.expected);
    assert.equal(rows.some((row) => row.slotHour === 14), false);
  }
});

test("v95 migration drops retired stored FX/H16 rows and rejects stale v94 public feeds", () => {
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
  assert.equal(parsePublicFeedCloudState({ ...buildPublicFeed(emptyCloudState()), signalRuleVersion: 94 }), null);
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
