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
  h1TargetBaseFromSymbol,
  h3EntrySignalDecision,
  mergeH1CloudStateHistory,
  parseCloudState,
  parsePublicFeedCloudState,
  scheduledSignalSlotForBrokerHour,
  scheduledSignalSlotForVietnamWall,
  signalBaseSourceForTarget,
  signalInvertedForTarget,
  targetsForBlockHour,
  type H1H3EntrySignalContext,
  type H1LocalMarketSnapshot,
} from "./h1-cloud-scanner.ts";
import type { H1M15Bar } from "./h1-local-patterns.ts";

const TARGETS = ["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const;

function candle(date: string, hour: number, minute: number, direction: "T" | "G", seed = 100): H1M15Bar {
  const open = seed;
  const close = direction === "T" ? open + 1 : open - 1;
  return { brokerDate: date, hour, minute, direction, open, high: Math.max(open, close) + 0.2, low: Math.min(open, close) - 0.2, close };
}

function patternBars(date: string, slotHour = 3, sequence = "TTGTTT", family: "ALT" | "SAME" = "ALT"): H1M15Bar[] {
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

function market(date: string, slotHour = 3, sequence = "TTGTTT", family: "ALT" | "SAME" = "ALT"): H1LocalMarketSnapshot {
  return {
    XAUUSD: { displayName: "XAUUSD", bars: patternBars(date, slotHour, sequence, family) },
    GBPUSD: { displayName: "GBPUSD", bars: [] },
    AUDUSD: { displayName: "AUDUSD", bars: [] },
    USDCAD: { displayName: "USDCAD", bars: [] },
    USDJPY: { displayName: "USDJPY", bars: [] },
  };
}

function setBase(snapshot: H1LocalMarketSnapshot, symbol: typeof TARGETS[number], date: string, hour: number, minute: number, direction: "T" | "G") {
  snapshot[symbol].bars = [
    ...snapshot[symbol].bars.filter((bar) => !(bar.brokerDate === date && bar.hour === hour && bar.minute === minute)),
    candle(date, hour, minute, direction, 500 + hour + minute / 100),
  ];
}

function alertFor(snapshot: H1LocalMarketSnapshot, target: typeof TARGETS[number], date: string, slotHour: number, context: H1H3EntrySignalContext) {
  return evaluateLocalH1PatternsForTarget(target, date, snapshot, [slotHour], slotHour, context)[0];
}

const KEEP_PREV: H1H3EntrySignalContext = { previousH3EntryHour: 4, currentH3EntryHour: 4 };
const INVERT_PREV: H1H3EntrySignalContext = { previousH3EntryHour: 5, currentH3EntryHour: 4 };
const KEEP_TODAY: H1H3EntrySignalContext = { previousH3EntryHour: 4, currentH3EntryHour: 4 };
const INVERT_TODAY: H1H3EntrySignalContext = { previousH3EntryHour: 4, currentH3EntryHour: 5 };

test("rule v90 keeps schema/state stable and removes H16 end-to-end", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 56);
  assert.equal(H1_PUBLIC_SCHEMA, 18);
  assert.equal(H1_SIGNAL_RULE_VERSION, 90);
  assert.equal(H1_CLOUD_PROFILE, "MT5 ICMarkets Local");
  assert.equal(H1_SCAN_END_HOUR, 14);
  assert.equal(H1_SIGNAL_END_HOUR, 14);
  assert.deepEqual(H1_SCAN_HOURS, [3, 6, 9, 12, 14]);
  assert.deepEqual(H1_TARGET_BASES, TARGETS);
  assert.deepEqual(targetsForBlockHour(16), []);
});

test("every row still uses its own M15 base and UC/UJ intrinsic inversion", () => {
  for (const target of TARGETS) assert.equal(signalBaseSourceForTarget(target), target);
  assert.equal(signalInvertedForTarget("XAUUSD"), false);
  assert.equal(signalInvertedForTarget("GBPUSD"), false);
  assert.equal(signalInvertedForTarget("AUDUSD"), false);
  assert.equal(signalInvertedForTarget("USDCAD"), true);
  assert.equal(signalInvertedForTarget("USDJPY"), true);
});

test("H3/H6/H9 policy uses previous broker-day H3 entry H4 keep and H5 invert", () => {
  for (const slotHour of [3, 6, 9]) {
    assert.deepEqual(h3EntrySignalDecision(slotHour, KEEP_PREV), { ready: true, inverted: false, rule: "h3-prev-h4-keep", referenceEntryHour: 4 });
    assert.deepEqual(h3EntrySignalDecision(slotHour, INVERT_PREV), { ready: true, inverted: true, rule: "h3-prev-h5-invert", referenceEntryHour: 5 });
  }
});

test("H12/H14 policy uses current broker-day H3 entry H4 keep and H5 invert", () => {
  for (const slotHour of [12, 14]) {
    assert.deepEqual(h3EntrySignalDecision(slotHour, KEEP_TODAY), { ready: true, inverted: false, rule: "h3-today-h4-keep", referenceEntryHour: 4 });
    assert.deepEqual(h3EntrySignalDecision(slotHour, INVERT_TODAY), { ready: true, inverted: true, rule: "h3-today-h5-invert", referenceEntryHour: 5 });
  }
});

test("H3/H6/H9 final signal applies previous-H3 inversion after own-symbol base rule", () => {
  const date = "2026-09-09";
  for (const slotHour of [3, 6, 9]) {
    const snapshot = market(date, slotHour, "TTGTTT", "ALT"); // BT => entry slot+1, base :45
    const baseHour = slotHour - 2;
    setBase(snapshot, "GBPUSD", date, baseHour, 45, "T");
    setBase(snapshot, "USDCAD", date, baseHour, 45, "T");
    const guKeep = alertFor(snapshot, "GBPUSD", date, slotHour, KEEP_PREV);
    const guFlip = alertFor(snapshot, "GBPUSD", date, slotHour, INVERT_PREV);
    const ucKeep = alertFor(snapshot, "USDCAD", date, slotHour, KEEP_PREV);
    const ucFlip = alertFor(snapshot, "USDCAD", date, slotHour, INVERT_PREV);
    assert.deepEqual([guKeep?.baseH1Signal, guKeep?.symbolH1Signal, guKeep?.postSignalRule], ["BUY", "BUY", "h3-prev-h4-keep"]);
    assert.deepEqual([guFlip?.baseH1Signal, guFlip?.symbolH1Signal, guFlip?.postSignalRule], ["BUY", "SELL", "h3-prev-h5-invert"]);
    assert.deepEqual([ucKeep?.baseH1Signal, ucKeep?.symbolH1Signal, ucKeep?.postSignalRule], ["BUY", "SELL", "h3-prev-h4-keep"]);
    assert.deepEqual([ucFlip?.baseH1Signal, ucFlip?.symbolH1Signal, ucFlip?.postSignalRule], ["BUY", "BUY", "h3-prev-h5-invert"]);
  }
});

test("H12/H14 final signal applies today's-H3 inversion after own-symbol base rule", () => {
  const date = "2026-09-09";
  for (const slotHour of [12, 14]) {
    const snapshot = market(date, slotHour, "TTGTTT", "ALT");
    const baseHour = slotHour - 2;
    setBase(snapshot, "AUDUSD", date, baseHour, 45, "G");
    setBase(snapshot, "USDJPY", date, baseHour, 45, "G");
    const auKeep = alertFor(snapshot, "AUDUSD", date, slotHour, KEEP_TODAY);
    const auFlip = alertFor(snapshot, "AUDUSD", date, slotHour, INVERT_TODAY);
    const ujKeep = alertFor(snapshot, "USDJPY", date, slotHour, KEEP_TODAY);
    const ujFlip = alertFor(snapshot, "USDJPY", date, slotHour, INVERT_TODAY);
    assert.deepEqual([auKeep?.baseH1Signal, auKeep?.symbolH1Signal, auKeep?.postSignalRule], ["SELL", "SELL", "h3-today-h4-keep"]);
    assert.deepEqual([auFlip?.baseH1Signal, auFlip?.symbolH1Signal, auFlip?.postSignalRule], ["SELL", "BUY", "h3-today-h5-invert"]);
    assert.deepEqual([ujKeep?.baseH1Signal, ujKeep?.symbolH1Signal, ujKeep?.postSignalRule], ["SELL", "BUY", "h3-today-h4-keep"]);
    assert.deepEqual([ujFlip?.baseH1Signal, ujFlip?.symbolH1Signal, ujFlip?.postSignalRule], ["SELL", "SELL", "h3-today-h5-invert"]);
  }
});

test("missing H3 selector fails closed instead of guessing KEEP", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 3, "TTGTTT", "ALT");
  setBase(snapshot, "GBPUSD", date, 1, 45, "T");
  const alert = alertFor(snapshot, "GBPUSD", date, 3, { previousH3EntryHour: null, currentH3EntryHour: 4 });
  assert.deepEqual([alert?.baseH1Signal, alert?.symbolH1Signal, alert?.postSignalRule], ["BUY", null, "h3-prev-pending"]);
});

test("exact own-symbol M15 base remains entry-2h15", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 9, "TGGTTT", "ALT"); // SW => H11, base 08:45
  setBase(snapshot, "AUDUSD", date, 8, 45, "T");
  const alert = alertFor(snapshot, "AUDUSD", date, 9, KEEP_PREV);
  assert.deepEqual([alert?.entryHour, alert?.baseSymbol, alert?.baseHour, alert?.baseMinute, alert?.signalBaseBar?.brokerTime], [11, "AUDUSD", 8, 45, "08:45"]);
});

test("H16 cannot be evaluated or published in v90", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 16, "TTGTTT", "ALT");
  for (const target of TARGETS) {
    assert.deepEqual(evaluateLocalH1PatternsForTarget(target, date, snapshot, [16], 16, KEEP_PREV), []);
  }
  assert.equal(scheduledSignalSlotForBrokerHour("XAUUSD", date, 16), 14);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 22, 4), 14);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 22, 5), null);
});

test("Telegram GBP-cross aliases still map to underlying v90 table rows", () => {
  assert.equal(h1TargetBaseFromSymbol("GBPAUD"), "AUDUSD");
  assert.equal(h1TargetBaseFromSymbol("GBPCAD.a"), "USDCAD");
  assert.equal(h1TargetBaseFromSymbol("GBPJPY"), "USDJPY");
});

test("cloud state v56 round-trips v90 H3 rule and OHLC evidence", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 3, "TTGTTT", "ALT");
  setBase(snapshot, "USDCAD", date, 1, 45, "T");
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "USDCAD").symbol.alerts.push(alertFor(snapshot, "USDCAD", date, 3, INVERT_PREV));
  const stored = parseCloudState(JSON.stringify(state)).days[date].symbols.USDCAD?.alerts[0];
  assert.deepEqual([stored?.baseH1Signal, stored?.symbolH1Signal, stored?.postSignalRule, stored?.postSignalInverted], ["BUY", "BUY", "h3-prev-h5-invert", true]);
  assert.equal(stored?.signalBaseBar?.brokerTime, "01:45");
});

test("public feed schema 18 exposes v90 five-block H3 selector contract", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 12, "TTGTTT", "ALT");
  setBase(snapshot, "GBPUSD", date, 10, 45, "T");
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "GBPUSD").symbol.alerts.push(alertFor(snapshot, "GBPUSD", date, 12, INVERT_TODAY));
  const feed = buildPublicFeed(state, "2026-09-09T01:00:00.000Z");
  assert.deepEqual([feed.schemaVersion, feed.signalRuleVersion, feed.hours, feed.symbols], [18, 90, [3, 6, 9, 12, 14], TARGETS]);
  const row = feed.days[date].symbols.GBPUSD?.alerts[0];
  assert.deepEqual([row?.baseSignal, row?.signal, row?.postSignalRule, row?.postSignalInverted], ["BUY", "SELL", "h3-today-h5-invert", true]);
  const seeded = parsePublicFeedCloudState(feed);
  const seededRow = seeded?.days[date].symbols.GBPUSD?.alerts[0];
  assert.deepEqual([seededRow?.baseH1Signal, seededRow?.symbolH1Signal, seededRow?.postSignalRule], ["BUY", "SELL", "h3-today-h5-invert"]);
});

test("v90 parser rejects retained v89 local-pattern rows", () => {
  const date = "2026-09-09";
  const stale = emptyCloudState();
  ensureSymbolDay(stale, date, "GBPUSD").symbol.alerts.push({
    slotHour: 3, symbol: "GBPUSD", profile: H1_CLOUD_PROFILE, baseSymbol: "GBPUSD",
    baseH1Signal: "BUY", baseHour: 1, baseMinute: 45, baseDirection: "T", symbolH1Signal: "BUY",
    scheduledSignal: null, postSignalInverted: false, postSignalRule: "none", entryHour: 4,
    patternGroup: "BT", patternFamily: "ALT", pattern: "TTG", scannerSource: "XAUUSD", inversionBadge: false, sampleBars: [], signalBaseBar: null,
  });
  assert.deepEqual(parseCloudState(JSON.stringify(stale)).days[date].symbols.GBPUSD?.alerts, []);
  assert.equal(parsePublicFeedCloudState({ ...buildPublicFeed(emptyCloudState()), signalRuleVersion: 89 }), null);
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
