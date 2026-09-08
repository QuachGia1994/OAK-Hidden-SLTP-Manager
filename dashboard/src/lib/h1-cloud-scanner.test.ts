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
  mergeH1CloudStateHistory,
  parseCloudState,
  parsePublicFeedCloudState,
  scheduledSignalSlotForBrokerHour,
  scheduledSignalSlotForVietnamWall,
  signalBaseSourceForTarget,
  signalInvertedForTarget,
  targetsForBlockHour,
  type H1LocalMarketSnapshot,
} from "./h1-cloud-scanner.ts";
import type { H1M15Bar } from "./h1-local-patterns.ts";

const TARGETS = ["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const;

function candle(date: string, hour: number, minute: number, direction: "T" | "G", seed = 100): H1M15Bar {
  const open = seed;
  const close = direction === "T" ? open + 1 : open - 1;
  return {
    brokerDate: date,
    hour,
    minute,
    direction,
    open,
    high: Math.max(open, close) + 0.2,
    low: Math.min(open, close) - 0.2,
    close,
  };
}

function patternBars(
  date: string,
  slotHour = 3,
  sequence = "TTGTTT",
  family: "ALT" | "SAME" = "ALT",
): H1M15Bar[] {
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
  const xau = patternBars(date, slotHour, sequence, family);
  return {
    XAUUSD: { displayName: "XAUUSD", bars: xau },
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

function alertFor(snapshot: H1LocalMarketSnapshot, target: typeof TARGETS[number], date: string, slotHour: number) {
  return evaluateLocalH1PatternsForTarget(target, date, snapshot, [slotHour], slotHour)[0];
}

test("rule v89 uses local MT5 ICMarkets, schema 18 and five own-symbol M15 rows through H16", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 56);
  assert.equal(H1_PUBLIC_SCHEMA, 18);
  assert.equal(H1_SIGNAL_RULE_VERSION, 89);
  assert.equal(H1_CLOUD_PROFILE, "MT5 ICMarkets Local");
  assert.equal(H1_SCAN_END_HOUR, 16);
  assert.equal(H1_SIGNAL_END_HOUR, 16);
  assert.deepEqual(H1_SCAN_HOURS, [3, 6, 9, 12, 14, 16]);
  assert.deepEqual(H1_TARGET_BASES, TARGETS);
});

test("all five signal rows are eligible on every H1 block", () => {
  for (const hour of H1_SCAN_HOURS) assert.deepEqual(targetsForBlockHour(hour), TARGETS);
  assert.deepEqual(targetsForBlockHour(4), []);
});

test("every row uses its own symbol as the M15 base and only USDCAD/USDJPY invert", () => {
  for (const target of TARGETS) assert.equal(signalBaseSourceForTarget(target), target);
  assert.equal(signalInvertedForTarget("XAUUSD"), false);
  assert.equal(signalInvertedForTarget("GBPUSD"), false);
  assert.equal(signalInvertedForTarget("AUDUSD"), false);
  assert.equal(signalInvertedForTarget("USDCAD"), true);
  assert.equal(signalInvertedForTarget("USDJPY"), true);
});

test("BT H3 entry H4 reads exact own-symbol M15 01:45", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 3, "TTGTTT", "ALT");
  setBase(snapshot, "GBPUSD", date, 1, 45, "T");
  setBase(snapshot, "AUDUSD", date, 1, 45, "G");
  setBase(snapshot, "USDCAD", date, 1, 45, "T");
  setBase(snapshot, "USDJPY", date, 1, 45, "G");

  const expected = {
    XAUUSD: ["XAUUSD", "G", "SELL"],
    GBPUSD: ["GBPUSD", "T", "BUY"],
    AUDUSD: ["AUDUSD", "G", "SELL"],
    USDCAD: ["USDCAD", "T", "SELL"],
    USDJPY: ["USDJPY", "G", "BUY"],
  } as const;

  for (const target of TARGETS) {
    const alert = alertFor(snapshot, target, date, 3);
    assert.deepEqual(
      [alert?.entryHour, alert?.baseSymbol, alert?.baseHour, alert?.baseMinute, alert?.baseDirection, alert?.symbolH1Signal],
      [4, expected[target][0], 1, 45, expected[target][1], expected[target][2]],
    );
    assert.equal(alert?.signalBaseBar?.brokerTime, "01:45");
    assert.equal(alert?.signalBaseBar?.brokerDate, date);
  }
});

test("explicit H11:00 example reads each row's own M15 08:45", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 9, "TGGTTT", "ALT"); // SW => entry H11
  setBase(snapshot, "XAUUSD", date, 8, 45, "T");
  setBase(snapshot, "GBPUSD", date, 8, 45, "G");
  setBase(snapshot, "AUDUSD", date, 8, 45, "T");
  setBase(snapshot, "USDCAD", date, 8, 45, "T");
  setBase(snapshot, "USDJPY", date, 8, 45, "G");

  const expectedSignal = { XAUUSD: "BUY", GBPUSD: "SELL", AUDUSD: "BUY", USDCAD: "SELL", USDJPY: "BUY" } as const;
  for (const target of TARGETS) {
    const alert = alertFor(snapshot, target, date, 9);
    assert.deepEqual([alert?.entryHour, alert?.baseSymbol, alert?.baseHour, alert?.baseMinute, alert?.symbolH1Signal], [11, target, 8, 45, expectedSignal[target]]);
  }
});

test("v89 never falls back to a previous broker day for signal base", () => {
  const monday = "2026-09-07";
  const friday = "2026-09-04";
  const snapshot = market(monday, 3, "TTGTTT", "ALT");
  setBase(snapshot, "AUDUSD", friday, 1, 45, "T");
  const missing = alertFor(snapshot, "AUDUSD", monday, 3);
  assert.equal(missing?.entryHour, 4);
  assert.equal(missing?.baseSymbol, "AUDUSD");
  assert.deepEqual([missing?.baseHour, missing?.baseMinute, missing?.baseDirection, missing?.symbolH1Signal], [1, 45, "", null]);

  setBase(snapshot, "AUDUSD", monday, 1, 45, "G");
  const sameDay = alertFor(snapshot, "AUDUSD", monday, 3);
  assert.deepEqual([sameDay?.baseDirection, sameDay?.symbolH1Signal], ["G", "SELL"]);
});

test("row base availability never changes the shared XAU entry time", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 9, "TGGTTT", "ALT");
  for (const target of TARGETS) {
    const alert = alertFor(snapshot, target, date, 9);
    assert.equal(alert?.entryHour, 11);
    assert.equal(alert?.scannerSource, "XAUUSD");
  }
});

test("H16 computes BUY/SELL from own M15 base while Telegram slot mapping still stops at H14", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 16, "TTGTTT", "ALT");
  const xau = alertFor(snapshot, "XAUUSD", date, 16);
  assert.ok(Number.isInteger(xau?.entryHour));
  const totalMinutes = Number(xau?.entryHour) * 60 - 135;
  const baseHour = Math.floor(totalMinutes / 60);
  const baseMinute = totalMinutes % 60;
  assert.deepEqual([xau?.baseSymbol, xau?.baseHour, xau?.baseMinute], ["XAUUSD", baseHour, 45]);
  assert.ok(xau?.symbolH1Signal === "BUY" || xau?.symbolH1Signal === "SELL");

  for (const target of ["GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const) {
    setBase(snapshot, target, date, baseHour, baseMinute, "T");
    const alert = alertFor(snapshot, target, date, 16);
    assert.deepEqual(
      [alert?.entryHour, alert?.baseSymbol, alert?.baseHour, alert?.baseMinute, alert?.symbolH1Signal],
      [xau?.entryHour, target, baseHour, 45, signalInvertedForTarget(target) ? "SELL" : "BUY"],
    );
  }
  assert.equal(scheduledSignalSlotForBrokerHour("XAUUSD", date, 16), 14);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 22, 4), 14);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 22, 5), null);
});

test("Telegram target parsing preserves GBP-cross routing onto the new underlying rows", () => {
  const date = "2026-09-09";
  assert.equal(h1TargetBaseFromSymbol("xauusd+"), "XAUUSD");
  assert.equal(h1TargetBaseFromSymbol("AUDUSD.a"), "AUDUSD");
  assert.equal(h1TargetBaseFromSymbol("USDCAD"), "USDCAD");
  assert.equal(h1TargetBaseFromSymbol("USDJPY.pro"), "USDJPY");
  assert.equal(h1TargetBaseFromSymbol("GBPAUD"), "AUDUSD");
  assert.equal(h1TargetBaseFromSymbol("GBPCAD.a"), "USDCAD");
  assert.equal(h1TargetBaseFromSymbol("GBPJPY"), "USDJPY");
  assert.equal(scheduledSignalSlotForVietnamWall("AUDUSD", date, 15, 5), 9);
});

test("cloud state v56 round-trips v89 base minute and exact OHLC evidence", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 3, "TTGTTT", "ALT");
  setBase(snapshot, "AUDUSD", date, 1, 45, "T");
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "AUDUSD").symbol.alerts.push(alertFor(snapshot, "AUDUSD", date, 3));

  const stored = parseCloudState(JSON.stringify(state)).days[date].symbols.AUDUSD?.alerts[0];
  assert.deepEqual([stored?.entryHour, stored?.baseSymbol, stored?.baseHour, stored?.baseMinute, stored?.baseH1Signal, stored?.symbolH1Signal], [4, "AUDUSD", 1, 45, "BUY", "BUY"]);
  assert.equal(stored?.signalBaseBar?.brokerTime, "01:45");
  assert.throws(() => parseCloudState({ version: 55, days: {} }), /schema/i);
});

test("public feed schema 18 exposes v89 own-symbol M15 signals and can seed state", () => {
  const date = "2026-09-09";
  const snapshot = market(date, 3, "TTGTTT", "ALT");
  setBase(snapshot, "USDCAD", date, 1, 45, "T");
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "USDCAD").symbol.alerts.push(alertFor(snapshot, "USDCAD", date, 3));

  const feed = buildPublicFeed(state, "2026-09-09T01:00:00.000Z");
  assert.deepEqual([feed.schemaVersion, feed.signalRuleVersion, feed.hours, feed.symbols], [18, 89, [3, 6, 9, 12, 14, 16], TARGETS]);
  const row = feed.days[date].symbols.USDCAD?.alerts[0];
  assert.deepEqual([row?.entryHour, row?.baseSymbol, row?.baseHour, row?.baseMinute, row?.baseSignal, row?.signal], [4, "USDCAD", 1, 45, "BUY", "SELL"]);
  assert.equal(row?.signalBaseBar?.brokerTime, "01:45");

  const seeded = parsePublicFeedCloudState(feed);
  const seededRow = seeded?.days[date].symbols.USDCAD?.alerts[0];
  assert.deepEqual([seededRow?.baseH1Signal, seededRow?.symbolH1Signal, seededRow?.baseMinute], ["BUY", "SELL", 45]);
  assert.equal(seededRow?.signalBaseBar?.brokerTime, "01:45");
});

test("public-feed reader rejects v88 payloads instead of relabeling old logic", () => {
  const feed = buildPublicFeed(emptyCloudState());
  assert.equal(parsePublicFeedCloudState({ ...feed, signalRuleVersion: 88 }), null);
});

test("state parser strips retired GBP-cross rows and stale v88 local-pattern rows", () => {
  const date = "2026-09-09";
  const stale = emptyCloudState() as unknown as { version: 56; days: Record<string, { symbols: Record<string, { alerts: unknown[] }> }> };
  stale.days[date] = {
    symbols: {
      GBPAUD: { alerts: [] },
      XAUUSD: { alerts: [{
        slotHour: 3, symbol: "XAUUSD", profile: H1_CLOUD_PROFILE, baseSymbol: "GBPUSD",
        baseH1Signal: "BUY", baseHour: 2, baseMinute: 0, baseDirection: "T", symbolH1Signal: "BUY",
        scheduledSignal: null, postSignalInverted: false, postSignalRule: "none", entryHour: 4,
        patternGroup: "BT", patternFamily: "ALT", pattern: "TTG", scannerSource: "XAUUSD", inversionBadge: false, sampleBars: [],
      }] },
    },
  };
  const parsed = parseCloudState(JSON.stringify(stale));
  assert.equal(Object.hasOwn(parsed.days[date].symbols, "GBPAUD"), false);
  assert.deepEqual(parsed.days[date].symbols.XAUUSD?.alerts, []);
});

test("rule bumps keep H1 history on the schema-stable state key", () => {
  assert.equal(H1_CLOUD_STATE_KEY, `robot-sltp:cloud:h1-scanner:state:s${H1_CLOUD_STATE_VERSION}`);
  assert.deepEqual(H1_LEGACY_CLOUD_STATE_KEYS, [
    "robot-sltp:cloud:h1-scanner:state:v73",
    "robot-sltp:cloud:h1-scanner:state:v72",
  ]);
});

test("history merge retains v89 broker days", () => {
  const oldDate = "2026-09-08";
  const currentDate = "2026-09-09";
  const history = emptyCloudState();
  history.days[oldDate] = { symbols: { XAUUSD: { alerts: [] } } };
  const current = emptyCloudState();
  current.days[currentDate] = { symbols: { XAUUSD: { alerts: [] } } };
  const merged = mergeH1CloudStateHistory(history, current);
  assert.deepEqual(Object.keys(merged.days).sort(), [oldDate, currentDate]);
});
