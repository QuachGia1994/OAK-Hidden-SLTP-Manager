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
import * as scannerModule from "./h1-cloud-scanner.ts";

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
  previousEntry: { brokerDate: string; slotHour: number; entryHour: number } | null = null,
) {
  return evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [slotHour], slotHour, previousEntry)[0];
}

function marketForSlots(date: string, cases: ReadonlyArray<readonly [number, string]>): H1LocalMarketSnapshot {
  const snapshot = market(date, cases[0]?.[0] ?? 3, cases[0]?.[1] ?? "TTGTTT");
  snapshot.XAUUSD.bars = cases.flatMap(([slotHour, sequence]) => patternBars(date, slotHour, sequence));
  return snapshot;
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

test("rule v97 keeps schema/state stable, exposes two public signal rows and removes H16", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 56);
  assert.equal(H1_PUBLIC_SCHEMA, 18);
  assert.equal(H1_SIGNAL_RULE_VERSION, 97);
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

test("previous-entry seed for H3 resolves the prior trading day's H14 entry across weekends", () => {
  const state = emptyCloudState();
  state.days["2026-09-11"] = { symbols: { XAUUSD: { alerts: [storedXauAlert(14, 2, "BUY")] } } };
  const previousH1EntryReferenceForDate = (scannerModule as typeof scannerModule & {
    previousH1EntryReferenceForDate?: (value: typeof state, brokerDate: string) => { brokerDate: string; slotHour: number; entryHour: number } | null;
  }).previousH1EntryReferenceForDate;
  assert.equal(typeof previousH1EntryReferenceForDate, "function");
  assert.deepEqual(previousH1EntryReferenceForDate?.(state, "2026-09-14"), { brokerDate: "2026-09-11", slotHour: 14, entryHour: 16 });
});

test("cloud state v56 round-trips v97 internal XAU GBPUSD-M15 base evidence", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 12, "TTGTTT");
  setM15(snapshot, "GBPUSD", date, 12, 45, "T");
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push(alertFor(snapshot, date, 12));
  const stored = parseCloudState(JSON.stringify(state)).days[date].symbols.XAUUSD?.alerts[0];
  assert.deepEqual([stored?.baseSymbol, stored?.baseHour, stored?.baseMinute, stored?.baseH1Signal, stored?.symbolH1Signal, stored?.postSignalRule], ["GBPUSD", 12, 45, "BUY", "SELL", "block-base-invert"]);
  assert.equal(stored?.signalBaseBar?.brokerTime, "12:45");
});

test("public feed schema 18 hides XAUUSD signal and cross-links previous-entry H1 bases", () => {
  const date = "2026-09-09";
  const previousDate = "2026-09-08";
  const snapshot = market(date, 3, "TTGTTT");
  setH1(snapshot, "GBPUSD", previousDate, 16, "T");
  setH1(snapshot, "GBPAUD", previousDate, 16, "G");
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push(alertFor(snapshot, date, 3, { brokerDate: previousDate, slotHour: 14, entryHour: 16 }));
  const feed = buildPublicFeed(state, "2026-09-09T01:00:00.000Z");
  assert.deepEqual([feed.schemaVersion, feed.signalRuleVersion, feed.hours, feed.symbols], [18, 97, [3, 6, 9, 12, 14], ["GBPUSD", "GBPAUD"]]);
  assert.equal("XAUUSD" in feed.days[date].symbols, false);
  const gbpUsd = feed.days[date].symbols.GBPUSD?.alerts[0];
  const gbpAud = feed.days[date].symbols.GBPAUD?.alerts[0];
  assert.deepEqual([gbpUsd?.entryHour, gbpUsd?.baseSymbol, gbpUsd?.baseHour, gbpUsd?.baseMinute, gbpUsd?.baseSignal, gbpUsd?.signal, gbpUsd?.postSignalInverted, gbpUsd?.signalBaseBar?.brokerDate], [4, "GBPAUD", 16, 0, "SELL", "SELL", false, previousDate]);
  assert.deepEqual([gbpAud?.entryHour, gbpAud?.baseSymbol, gbpAud?.baseHour, gbpAud?.baseMinute, gbpAud?.baseSignal, gbpAud?.signal, gbpAud?.postSignalInverted, gbpAud?.signalBaseBar?.brokerDate], [4, "GBPUSD", 16, 0, "BUY", "SELL", true, previousDate]);

  const seeded = parsePublicFeedCloudState(feed);
  const seededOwner = seeded?.days[date]?.symbols.XAUUSD?.alerts[0];
  assert.ok(seededOwner, "v97 public replica must reconstruct the internal XAU entry owner");
  assert.equal(seededOwner.entryHour, 4);
  assert.equal(seededOwner.symbolH1Signal, null);
  assert.deepEqual(
    [seededOwner.ownH1Signals?.GBPUSD?.symbolH1Signal, seededOwner.ownH1Signals?.GBPAUD?.symbolH1Signal],
    ["SELL", "SELL"],
  );
  assert.deepEqual(buildPublicFeed(seeded!).days[date].symbols, feed.days[date].symbols);
});

test("each public signal uses the immediately previous XAU entry hour with cross-symbol KEEP/INVERT", () => {
  const date = "2026-09-09";
  const previousDate = "2026-09-08";
  const snapshot = marketForSlots(date, [[3, "TGGTTT"], [6, "TTGTTT"], [9, "TGGTTT"], [12, "TTGTTT"], [14, "TGGTTT"]]);

  // H3 consumes the prior trading day's H14 Entry H16.
  setH1(snapshot, "GBPUSD", previousDate, 16, "T");
  setH1(snapshot, "GBPAUD", previousDate, 16, "G");
  // H6 consumes H3 Entry H5; later blocks consume H6/H9/H12 entry hours in sequence.
  for (const hour of [5, 7, 11, 13]) {
    setH1(snapshot, "GBPUSD", date, hour, "G");
    setH1(snapshot, "GBPAUD", date, hour, "T");
  }

  const alerts = evaluateLocalH1PatternsForTarget(
    "XAUUSD",
    date,
    snapshot,
    [3, 6, 9, 12, 14],
    14,
    { brokerDate: previousDate, slotHour: 14, entryHour: 16 },
  );
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push(...alerts);
  const feed = buildPublicFeed(state);

  const expectedPreviousEntries = [16, 5, 7, 11, 13];
  for (const [index, slotHour] of [3, 6, 9, 12, 14].entries()) {
    const gbpUsd = feed.days[date].symbols.GBPUSD?.alerts[index];
    const gbpAud = feed.days[date].symbols.GBPAUD?.alerts[index];
    const baseHour = expectedPreviousEntries[index];
    assert.deepEqual([gbpUsd?.slotHour, gbpUsd?.baseSymbol, gbpUsd?.baseHour, gbpUsd?.baseSignal, gbpUsd?.signal], [slotHour, "GBPAUD", baseHour, index === 0 ? "SELL" : "BUY", index === 0 ? "SELL" : "BUY"]);
    assert.deepEqual([gbpAud?.slotHour, gbpAud?.baseSymbol, gbpAud?.baseHour, gbpAud?.baseSignal, gbpAud?.signal], [slotHour, "GBPUSD", baseHour, index === 0 ? "BUY" : "SELL", index === 0 ? "SELL" : "BUY"]);
  }
});

test("H3 signal fails closed without the previous H14 entry while XAU entry evidence remains", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 3, "TTGTTT");
  setH1(snapshot, "GBPUSD", date, 2, "T");
  setH1(snapshot, "GBPAUD", date, 2, "G");
  const alert = alertFor(snapshot, date, 3);
  assert.equal(alert?.entryHour, 4);
  assert.equal(alert?.ownH1Signals?.GBPUSD?.symbolH1Signal, null);
  assert.equal(alert?.ownH1Signals?.GBPAUD?.symbolH1Signal, null);
});

test("v97 TP milestones keep XAU-owned due times while public GBP signals use previous-entry cross H1", () => {
  const date = "2026-09-10";
  const previousDate = "2026-09-09";
  const snapshot = marketForSlots(date, [[3, "TGGTTT"], [6, "TTGTTT"], [9, "TTGTTT"], [12, "TTGTTT"], [14, "TTGTTT"]]);
  for (const [hour, minute] of [[4, 45], [6, 45], [9, 45], [12, 45], [14, 45]] as const) setM15(snapshot, "GBPUSD", date, hour, minute, "T");
  setH1(snapshot, "GBPUSD", previousDate, 16, "T");
  setH1(snapshot, "GBPAUD", previousDate, 16, "G");
  for (const hour of [5, 7, 10, 13]) {
    setH1(snapshot, "GBPUSD", date, hour, "G");
    setH1(snapshot, "GBPAUD", date, hour, "T");
  }
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push(...evaluateLocalH1PatternsForTarget(
    "XAUUSD",
    date,
    snapshot,
    [3, 6, 9, 12, 14],
    14,
    { brokerDate: previousDate, slotHour: 14, entryHour: 16 },
  ));
  const rows = h1TpRollMilestonesForBrokerDate(state, date);
  const gbpUsdH6 = rows.find((row) => row.symbol === "GBPUSD" && row.blockHour === 6);
  const gbpAudH14 = rows.find((row) => row.symbol === "GBPAUD" && row.blockHour === 14);
  assert.equal(gbpUsdH6?.entryHour, 7);
  assert.equal(gbpUsdH6?.side, "BUY");
  assert.equal(gbpUsdH6?.dueAt, Date.parse("2026-09-10T04:00:00.000Z"));
  assert.equal(gbpAudH14?.entryHour, 15);
  assert.equal(gbpAudH14?.side, "BUY");
  assert.equal(gbpAudH14?.dueAt, Date.parse("2026-09-10T12:00:00.000Z"));
  assert.equal(icMarketsBrokerWallEpochMs("2026-01-15", 7), Date.parse("2026-01-15T05:00:00.000Z"));
  assert.equal(icMarketsBrokerWallEpochMs("2026-09-10", 7), Date.parse("2026-09-10T04:00:00.000Z"));
});

test("v97 migration drops retired stored FX/H16 rows and rejects stale v96 public feeds", () => {
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
  assert.equal(parsePublicFeedCloudState({ ...buildPublicFeed(emptyCloudState()), signalRuleVersion: 96 }), null);
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
