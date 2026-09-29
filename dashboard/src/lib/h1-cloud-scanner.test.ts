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

function setH1(snapshot: H1LocalMarketSnapshot, symbol: keyof H1LocalMarketSnapshot, date: string, hour: number, direction: "T" | "G") {
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
  return evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, H1_SCAN_HOURS, slotHour)
    .find((alert) => alert.slotHour === slotHour);
}

test("rule v101 scans only H3/H4/H7/H10/H13/H16 with H3 as the pattern anchor", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 56);
  assert.equal(H1_PUBLIC_SCHEMA, 18);
  assert.equal(H1_SIGNAL_RULE_VERSION, 101);
  assert.equal(H1_CLOUD_PROFILE, "MT5 ICMarkets Local");
  assert.equal(H1_SCAN_END_HOUR, 16);
  assert.equal(H1_SIGNAL_END_HOUR, 16);
  assert.deepEqual(H1_SCAN_HOURS, [3, 4, 7, 10, 13, 16]);
  assert.deepEqual(H1_TARGET_BASES, ["XAUUSD"]);
});

test("scheduled XAUUSD signals map onto the six active H1 blocks", () => {
  const date = "2026-08-18";
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 9, 4), null);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 9, 5), 3);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 10, 5), 4);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 13, 5), 7);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 16, 5), 10);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 19, 5), 13);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 22, 5), 16);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 23, 59), 16);
  assert.equal(scheduledSignalSlotForBrokerHour("XAUUSD", date, 16), 16);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", "2026-08-16", 22, 5), null);
});

test("H3 remains pattern-driven: BT enters H4 and SW enters H5", () => {
  const date = "2026-08-18";
  const bt = market(date, 3, "TTGTTT");
  setM15(bt, "GBPUSD", date, 3, 45, "T");
  setH1(bt, "GBPAUD", date, 3, "T");
  const btAlert = alertFor(bt, date, 3);
  assert.deepEqual([btAlert?.slotHour, btAlert?.entryHour, btAlert?.baseSymbol, btAlert?.baseHour, btAlert?.baseMinute], [3, 4, "GBPUSD", 3, 45]);

  const sw = market(date, 3, "TGGTTT");
  setM15(sw, "GBPUSD", date, 4, 45, "G");
  setH1(sw, "GBPAUD", date, 4, "G");
  const swAlert = alertFor(sw, date, 3);
  assert.deepEqual([swAlert?.slotHour, swAlert?.entryHour, swAlert?.baseSymbol, swAlert?.baseHour, swAlert?.baseMinute], [3, 5, "GBPUSD", 4, 45]);
});

test("XAUUSD scanner evaluates reversals only at H4/H7/H10/H13/H16", () => {
  const date = "2026-08-18";
  const snapshot = market(date, 3);
  setH1(snapshot, "GBPAUD", date, 2, "G"); // Must not affect the XAU-only rule.
  setH1(snapshot, "GBPAUD", date, 3, "T");
  setH1(snapshot, "XAUUSD", date, 2, "T");
  setH1(snapshot, "XAUUSD", date, 3, "G");
  setH1(snapshot, "XAUUSD", date, 5, "T");
  setH1(snapshot, "XAUUSD", date, 6, "G");
  setH1(snapshot, "XAUUSD", date, 8, "G");
  setH1(snapshot, "XAUUSD", date, 9, "T");
  setH1(snapshot, "XAUUSD", date, 11, "T");
  setH1(snapshot, "XAUUSD", date, 12, "G");
  setH1(snapshot, "XAUUSD", date, 14, "G");
  setH1(snapshot, "XAUUSD", date, 15, "T");

  const alerts = evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, H1_SCAN_HOURS, 16);
  assert.deepEqual(alerts.filter((alert) => alert.slotHour >= 4).map((alert) => [alert.slotHour, alert.entryHour, alert.baseHour, alert.symbolH1Signal]), [
    [4, 4, 3, "SELL"],
    [7, 7, 6, "SELL"],
    [10, 10, 9, "BUY"],
    [13, 13, 12, "SELL"],
    [16, 16, 15, "BUY"],
  ]);
  assert.ok(alerts.filter((alert) => alert.slotHour >= 4).every((alert) => alert.baseSymbol === "XAUUSD"));
});

test("XAUUSD H1 reversal blocks fail closed without a two-candle reversal", () => {
  const date = "2026-08-18";
  const snapshot = market(date, 3);
  setH1(snapshot, "XAUUSD", date, 2, "T");
  setH1(snapshot, "XAUUSD", date, 3, "T");
  assert.deepEqual(evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [4], 4), []);
  setH1(snapshot, "XAUUSD", date, 3, "G");
  assert.equal(evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [5], 5).length, 0);
});

test("public feed publishes only XAUUSD across the six active blocks and round-trips", () => {
  const date = "2026-08-18";
  const snapshot = market(date, 3, "TTGTTT");
  setM15(snapshot, "GBPUSD", date, 3, 45, "T");
  setH1(snapshot, "GBPAUD", date, 3, "T");
  for (const [hour, direction] of [[2, "T"], [3, "G"], [5, "T"], [6, "G"], [8, "G"], [9, "T"], [11, "T"], [12, "G"], [14, "G"], [15, "T"]] as const) {
    setH1(snapshot, "XAUUSD", date, hour, direction);
  }
  const alerts = evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, H1_SCAN_HOURS, 16);
  const state = emptyCloudState();
  state.days[date] = { symbols: { XAUUSD: { alerts } } };

  const feed = buildPublicFeed(state);
  assert.deepEqual(feed.hours, [3, 4, 7, 10, 13, 16]);
  assert.deepEqual(feed.symbols, ["XAUUSD"]);
  assert.deepEqual(Object.keys(feed.days[date].symbols), ["XAUUSD"]);
  assert.deepEqual(feed.days[date].symbols.XAUUSD?.alerts.map((alert) => alert.slotHour), [3, 4, 7, 10, 13, 16]);

  const roundTrip = parsePublicFeedCloudState(feed);
  assert.deepEqual(roundTrip?.days[date].symbols.XAUUSD?.alerts.map((alert) => alert.slotHour), [3, 4, 7, 10, 13, 16]);
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
