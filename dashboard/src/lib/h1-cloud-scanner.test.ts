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
    AUDUSD: source("AUDUSD"),
    USDCAD: source("USDCAD"),
    USDJPY: source("USDJPY"),
  };
  snapshot.XAUUSD.bars = patternBars(date, slotHour, sequence);
  return snapshot;
}

function setH1(snapshot: H1LocalMarketSnapshot, symbol: keyof H1LocalMarketSnapshot, date: string, hour: number, direction: "T" | "G") {
  snapshot[symbol].h1Bars = [
    ...snapshot[symbol].h1Bars.filter((bar) => !(bar.brokerDate === date && bar.hour === hour)),
    candle(date, hour, 0, direction, 500 + hour),
  ];
}

function alertFor(snapshot: H1LocalMarketSnapshot, date: string, slotHour: number) {
  return evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [slotHour], slotHour)[0];
}

test("rule v91 keeps schema/state stable, exposes one XAU row and restores H16", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 56);
  assert.equal(H1_PUBLIC_SCHEMA, 18);
  assert.equal(H1_SIGNAL_RULE_VERSION, 91);
  assert.equal(H1_CLOUD_PROFILE, "MT5 ICMarkets Local");
  assert.equal(H1_SCAN_END_HOUR, 16);
  assert.equal(H1_SIGNAL_END_HOUR, 16);
  assert.deepEqual(H1_SCAN_HOURS, [3, 6, 9, 12, 14, 16]);
  assert.deepEqual(H1_TARGET_BASES, ["XAUUSD"]);
  assert.deepEqual(targetsForBlockHour(16), ["XAUUSD"]);
});

test("delta 1 looks back two H1 candles and delta 2 looks back one", () => {
  assert.deepEqual(h1BlockSignalPlan(3, 4), { baseSymbol: "AUDUSD", baseHour: 2, inverted: false, rule: "block-base-keep" });
  assert.deepEqual(h1BlockSignalPlan(3, 5), { baseSymbol: "AUDUSD", baseHour: 4, inverted: false, rule: "block-base-keep" });
  assert.deepEqual(h1BlockSignalPlan(6, 7), { baseSymbol: "GBPUSD", baseHour: 5, inverted: false, rule: "block-base-keep" });
  assert.deepEqual(h1BlockSignalPlan(6, 8), { baseSymbol: "GBPUSD", baseHour: 7, inverted: false, rule: "block-base-keep" });
});

test("all six blocks use the requested H1 source and KEEP/INVERT policy", () => {
  const date = "2026-09-09";
  const cases = [
    { slot: 3, source: "AUDUSD" as const, inverted: false, direction: "T" as const, expected: "BUY" },
    { slot: 6, source: "GBPUSD" as const, inverted: false, direction: "T" as const, expected: "BUY" },
    { slot: 9, source: "GBPUSD" as const, inverted: true, direction: "G" as const, expected: "BUY" },
    { slot: 12, source: "USDJPY" as const, inverted: true, direction: "T" as const, expected: "SELL" },
    { slot: 14, source: "USDCAD" as const, inverted: false, direction: "G" as const, expected: "SELL" },
    { slot: 16, source: "GBPUSD" as const, inverted: false, direction: "T" as const, expected: "BUY" },
  ];
  for (const item of cases) {
    const snapshot = market(date, item.slot, "TTGTTT"); // BT => entry block+1 => H1 base block-1
    const baseHour = item.slot - 1;
    setH1(snapshot, item.source, date, baseHour, item.direction);
    const alert = alertFor(snapshot, date, item.slot);
    assert.deepEqual(
      [alert?.entryHour, alert?.baseSymbol, alert?.baseHour, alert?.baseMinute, alert?.postSignalInverted, alert?.symbolH1Signal, alert?.signalBaseBar?.brokerTime],
      [item.slot + 1, item.source, baseHour, 0, item.inverted, item.expected, `${String(baseHour).padStart(2, "0")}:00`],
    );
  }
});

test("SW delta 2 uses entry-1 H1 rather than the delta-1 candle", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 3, "TGGTTT"); // SW => H5 => base H4
  setH1(snapshot, "AUDUSD", date, 2, "G");
  setH1(snapshot, "AUDUSD", date, 4, "T");
  const alert = alertFor(snapshot, date, 3);
  assert.deepEqual([alert?.entryHour, alert?.baseHour, alert?.baseH1Signal, alert?.symbolH1Signal], [5, 4, "BUY", "BUY"]);
});

test("entry evidence survives while signal fails closed until the required H1 candle exists", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 16, "TGGTTT"); // SW => H18, base GBPUSD H17
  const alert = alertFor(snapshot, date, 16);
  assert.deepEqual([alert?.entryHour, alert?.baseSymbol, alert?.baseHour, alert?.baseH1Signal, alert?.symbolH1Signal], [18, "GBPUSD", 17, null, null]);
  assert.ok((alert?.sampleBars?.length || 0) > 0);
});

test("H16 is calculation-only while Telegram table annotation keeps the existing H14 cutoff", () => {
  const date = "2026-09-09";
  assert.equal(scheduledSignalSlotForBrokerHour("XAUUSD", date, 16), 16);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 22, 4), 14);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 22, 5), null);
  assert.equal(h1TargetBaseFromSymbol("XAUUSD.a"), "XAUUSD");
  assert.equal(h1TargetBaseFromSymbol("GOLD"), "XAUUSD");
  assert.equal(h1TargetBaseFromSymbol("GBPUSD"), null);
  assert.equal(h1TargetBaseFromSymbol("GBPAUD"), null);
});

test("cloud state v56 round-trips v91 H1 base evidence", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 12, "TTGTTT");
  setH1(snapshot, "USDJPY", date, 11, "T");
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push(alertFor(snapshot, date, 12));
  const stored = parseCloudState(JSON.stringify(state)).days[date].symbols.XAUUSD?.alerts[0];
  assert.deepEqual([stored?.baseSymbol, stored?.baseHour, stored?.baseMinute, stored?.baseH1Signal, stored?.symbolH1Signal, stored?.postSignalRule], ["USDJPY", 11, 0, "BUY", "SELL", "block-base-invert"]);
  assert.equal(stored?.signalBaseBar?.brokerTime, "11:00");
});

test("public feed schema 18 exposes v91 one-row six-block contract", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 14, "TTGTTT");
  setH1(snapshot, "USDCAD", date, 13, "G");
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push(alertFor(snapshot, date, 14));
  const feed = buildPublicFeed(state, "2026-09-09T01:00:00.000Z");
  assert.deepEqual([feed.schemaVersion, feed.signalRuleVersion, feed.hours, feed.symbols], [18, 91, [3, 6, 9, 12, 14, 16], ["XAUUSD"]]);
  const row = feed.days[date].symbols.XAUUSD?.alerts[0];
  assert.deepEqual([row?.baseSymbol, row?.baseSignal, row?.signal, row?.postSignalRule, row?.postSignalInverted], ["USDCAD", "SELL", "SELL", "block-base-keep", false]);
  const seeded = parsePublicFeedCloudState(feed);
  const seededRow = seeded?.days[date].symbols.XAUUSD?.alerts[0];
  assert.deepEqual([seededRow?.baseSymbol, seededRow?.baseH1Signal, seededRow?.symbolH1Signal], ["USDCAD", "SELL", "SELL"]);
});

test("v91 migration drops retired FX rows and rejects stale v90 XAU calculations", () => {
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
  assert.equal(parsePublicFeedCloudState({ ...buildPublicFeed(emptyCloudState()), signalRuleVersion: 90 }), null);
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
