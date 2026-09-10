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
  mergeH1CloudStateHistory,
  parseCloudState,
  parsePublicFeedCloudState,
  scheduledSignalSlotForBrokerHour,
  scheduledSignalSlotForVietnamWall,
  targetsForBlockHour,
  type H1LocalMarketSnapshot,
} from "./h1-cloud-scanner.ts";
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

test("rule v94 keeps schema/state stable, exposes one XAU row and removes H16", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 56);
  assert.equal(H1_PUBLIC_SCHEMA, 18);
  assert.equal(H1_SIGNAL_RULE_VERSION, 94);
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

test("cloud state v56 round-trips v94 GBPUSD M15 base evidence", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 12, "TTGTTT");
  setM15(snapshot, "GBPUSD", date, 12, 45, "T");
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push(alertFor(snapshot, date, 12));
  const stored = parseCloudState(JSON.stringify(state)).days[date].symbols.XAUUSD?.alerts[0];
  assert.deepEqual([stored?.baseSymbol, stored?.baseHour, stored?.baseMinute, stored?.baseH1Signal, stored?.symbolH1Signal, stored?.postSignalRule], ["GBPUSD", 12, 45, "BUY", "SELL", "block-base-invert"]);
  assert.equal(stored?.signalBaseBar?.brokerTime, "12:45");
});

test("public feed schema 18 exposes v94 one-row five-block contract", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 14, "TTGTTT");
  setM15(snapshot, "GBPUSD", date, 14, 45, "G");
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push(alertFor(snapshot, date, 14));
  const feed = buildPublicFeed(state, "2026-09-09T01:00:00.000Z");
  assert.deepEqual([feed.schemaVersion, feed.signalRuleVersion, feed.hours, feed.symbols], [18, 94, [3, 6, 9, 12, 14], ["XAUUSD"]]);
  const row = feed.days[date].symbols.XAUUSD?.alerts[0];
  assert.deepEqual([row?.baseSymbol, row?.baseHour, row?.baseMinute, row?.baseSignal, row?.signal, row?.postSignalRule, row?.postSignalInverted], ["GBPUSD", 14, 45, "SELL", "BUY", "block-base-invert", true]);
  const seeded = parsePublicFeedCloudState(feed);
  const seededRow = seeded?.days[date].symbols.XAUUSD?.alerts[0];
  assert.deepEqual([seededRow?.baseSymbol, seededRow?.baseH1Signal, seededRow?.symbolH1Signal], ["GBPUSD", "SELL", "BUY"]);
});

test("v94 migration drops retired FX/H16 rows and rejects stale v93 XAU calculations", () => {
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
  assert.equal(parsePublicFeedCloudState({ ...buildPublicFeed(emptyCloudState()), signalRuleVersion: 93 }), null);
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
