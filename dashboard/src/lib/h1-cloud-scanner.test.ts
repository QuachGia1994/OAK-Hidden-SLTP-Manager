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
  return rows.map(([hour, minute, direction], index) => {
    const open = 200 + index;
    const close = direction === "T" ? open + 0.8 : open - 0.8;
    return {
      brokerDate: date,
      hour,
      minute,
      direction,
      open,
      high: Math.max(open, close) + 0.3,
      low: Math.min(open, close) - 0.3,
      close,
    };
  });
}

function market(date: string, sequence = "TGTGTG", family: "ALT" | "SAME" = "ALT"): H1LocalMarketSnapshot {
  const sourceBars = bars(date, sequence, family);
  return {
    XAUUSD: { displayName: "XAUUSD", bars: sourceBars.filter((row) => !(family === "ALT" && row.hour === 1 && row.minute === 0)) },
    GBPUSD: { displayName: "GBPUSD", bars: sourceBars },
    GBPAUD: { displayName: "GBPAUD", bars: sourceBars },
    GBPCAD: { displayName: "GBPCAD", bars: sourceBars },
    GBPJPY: { displayName: "GBPJPY", bars: sourceBars },
  };
}

function h1Bars(date: string, hour: number, direction: "T" | "G"): H1M15Bar[] {
  return [0, 15, 30, 45].map((minute, index) => {
    const open = 500 + index * 0.1;
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
  });
}

function setOwnSignalHour(snapshot: H1LocalMarketSnapshot, symbol: string, date: string, hour: number, direction: "T" | "G") {
  const market = snapshot as unknown as Record<string, { displayName: string; bars: H1M15Bar[] }>;
  const current = market[symbol] || { displayName: symbol, bars: [] };
  market[symbol] = { ...current, bars: [...current.bars, ...h1Bars(date, hour, direction)] };
}

test("rule v86 uses local MT5 ICMarkets, schema 18 and six blocks with H16 entry-only", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 56);
  assert.equal(H1_PUBLIC_SCHEMA, 18);
  assert.equal(H1_SIGNAL_RULE_VERSION, 86);
  assert.equal(H1_CLOUD_PROFILE, "MT5 ICMarkets Local");
  assert.equal(H1_SCAN_END_HOUR, 16);
  assert.equal(H1_SIGNAL_END_HOUR, 14);
  assert.deepEqual(H1_SCAN_HOURS, [3, 6, 9, 12, 14, 16]);
  assert.deepEqual(H1_TARGET_BASES, ["XAUUSD", "GBPUSD", "GBPAUD", "GBPCAD", "GBPJPY"]);
});

test("all five rows are eligible on every H1 block and H16 is restored", () => {
  assert.deepEqual(targetsForBlockHour(3), [...H1_TARGET_BASES]);
  assert.deepEqual(targetsForBlockHour(6), [...H1_TARGET_BASES]);
  assert.deepEqual(targetsForBlockHour(9), [...H1_TARGET_BASES]);
  assert.deepEqual(targetsForBlockHour(12), [...H1_TARGET_BASES]);
  assert.deepEqual(targetsForBlockHour(14), [...H1_TARGET_BASES]);
  assert.deepEqual(targetsForBlockHour(16), [...H1_TARGET_BASES]);
  assert.deepEqual(targetsForBlockHour(4), []);
});

test("XAU H3 entry H4 is copied to GBP crosses and signal appears from each symbol own H3 candle", () => {
  const date = "2026-09-08";
  const snapshot = market(date, "TTGTTT", "ALT");

  const beforeClose = evaluateLocalH1PatternsForTarget("GBPAUD", date, snapshot, [3], 3)[0];
  assert.deepEqual(
    [beforeClose?.slotHour, beforeClose?.entryHour, beforeClose?.scannerSource, beforeClose?.baseSymbol, beforeClose?.baseHour, beforeClose?.baseH1Signal, beforeClose?.symbolH1Signal],
    [3, 4, "XAUUSD", "GBPAUD", 3, null, null],
  );

  setOwnSignalHour(snapshot, "GBPAUD", date, 3, "T");
  setOwnSignalHour(snapshot, "GBPCAD", date, 3, "G");
  setOwnSignalHour(snapshot, "GBPJPY", date, 3, "T");
  const aud = evaluateLocalH1PatternsForTarget("GBPAUD", date, snapshot, [3], 4)[0];
  const cad = evaluateLocalH1PatternsForTarget("GBPCAD", date, snapshot, [3], 4)[0];
  const jpy = evaluateLocalH1PatternsForTarget("GBPJPY", date, snapshot, [3], 4)[0];
  assert.deepEqual([aud?.entryHour, aud?.baseSymbol, aud?.baseHour, aud?.baseDirection, aud?.symbolH1Signal], [4, "GBPAUD", 3, "T", "BUY"]);
  assert.deepEqual([cad?.entryHour, cad?.baseSymbol, cad?.baseHour, cad?.baseDirection, cad?.symbolH1Signal], [4, "GBPCAD", 3, "G", "SELL"]);
  assert.deepEqual([jpy?.entryHour, jpy?.baseSymbol, jpy?.baseHour, jpy?.baseDirection, jpy?.symbolH1Signal], [4, "GBPJPY", 3, "T", "BUY"]);
});

test("all eligible H9 rows copy XAU entry time but derive independent same-day H(entry-1) signals", () => {
  const date = "2026-09-08";
  const snapshot = market(date, "TTGTTT", "ALT");
  snapshot.XAUUSD.bars = snapshot.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + 6 }));
  const directions = new Map([
    ["XAUUSD", "T"], ["GBPUSD", "G"], ["GBPAUD", "G"], ["GBPCAD", "T"], ["GBPJPY", "G"],
  ] as const);
  for (const [symbol, direction] of directions) setOwnSignalHour(snapshot, symbol, date, 9, direction);

  for (const base of H1_TARGET_BASES) {
    const alert = evaluateLocalH1PatternsForTarget(base, date, snapshot, [9], 10)[0];
    const direction = directions.get(base)!;
    assert.deepEqual(
      [alert?.entryHour, alert?.scannerSource, alert?.baseSymbol, alert?.baseHour, alert?.baseDirection, alert?.baseH1Signal, alert?.symbolH1Signal],
      [10, "XAUUSD", base, 9, direction, direction === "T" ? "BUY" : "SELL", direction === "T" ? "BUY" : "SELL"],
    );
  }
});

test("XAUUSD signal reads its own same-day candle immediately before BT or SW entry", () => {
  const date = "2026-09-08";

  const bt = market(date, "TTGTTT", "ALT");
  bt.XAUUSD.bars = bt.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + 3 }));
  setOwnSignalHour(bt, "XAUUSD", date, 6, "T");
  const btAlert = evaluateLocalH1PatternsForTarget("XAUUSD", date, bt, [6], 7)[0];
  assert.deepEqual([btAlert?.entryHour, btAlert?.baseSymbol, btAlert?.baseHour, btAlert?.baseDirection, btAlert?.symbolH1Signal], [7, "XAUUSD", 6, "T", "BUY"]);

  const sw = market(date, "TGGTTT", "ALT");
  sw.XAUUSD.bars = sw.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + 3 }));
  setOwnSignalHour(sw, "XAUUSD", date, 7, "G");
  const swAlert = evaluateLocalH1PatternsForTarget("XAUUSD", date, sw, [6], 8)[0];
  assert.deepEqual([swAlert?.entryHour, swAlert?.baseSymbol, swAlert?.baseHour, swAlert?.baseDirection, swAlert?.symbolH1Signal], [8, "XAUUSD", 7, "G", "SELL"]);
});

test("FX entry time depends only on the XAU pattern", () => {
  const date = "2026-09-08";
  const snapshot = market(date, "TTGTTT", "ALT");
  setOwnSignalHour(snapshot, "GBPAUD", date, 3, "T");
  setOwnSignalHour(snapshot, "GBPCAD", date, 3, "G");
  setOwnSignalHour(snapshot, "GBPJPY", date, 3, "T");

  for (const base of ["GBPAUD", "GBPCAD", "GBPJPY"] as const) {
    const alert = evaluateLocalH1PatternsForTarget(base, date, snapshot, [3], 4)[0];
    assert.equal(alert?.entryHour, 4);
    assert.equal(alert?.scannerSource, "XAUUSD");
    assert.equal(alert?.baseSymbol, base);
  }
});

test("all three GBP crosses copy the XAU entry hour on every eligible block", () => {
  const date = "2026-09-08";
  for (const slotHour of H1_SCAN_HOURS) {
    const snapshot = market(date, "TTGTTT", "ALT");
    const shift = slotHour - 3;
    snapshot.XAUUSD.bars = snapshot.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + shift }));
    const entryHour = slotHour + 1;
    for (const target of ["GBPAUD", "GBPCAD", "GBPJPY"] as const) {
      setOwnSignalHour(snapshot, target, date, entryHour - 1, "T");
      const alert = evaluateLocalH1PatternsForTarget(target, date, snapshot, [slotHour], entryHour)[0];
      assert.equal(alert?.entryHour, entryHour);
      assert.equal(alert?.scannerSource, "XAUUSD");
      assert.equal(alert?.baseSymbol, target);
      assert.equal(alert?.baseHour, entryHour - 1);
      assert.equal(alert?.symbolH1Signal, slotHour === 16 ? null : "BUY");
      if (slotHour === 16) assert.deepEqual([alert?.baseH1Signal, alert?.baseDirection], [null, ""]);
    }
  }
});

test("different FX candle directions never change the shared XAU entry hour", () => {
  const date = "2026-09-08";
  const slotHour = 9;
  const snapshot = market(date, "TGGTTT", "ALT");
  snapshot.XAUUSD.bars = snapshot.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + 6 }));
  for (const [target, direction] of [["GBPAUD", "T"], ["GBPCAD", "G"], ["GBPJPY", "T"]] as const) {
    setOwnSignalHour(snapshot, target, date, 10, direction);
    const alert = evaluateLocalH1PatternsForTarget(target, date, snapshot, [slotHour], 11)[0];
    assert.equal(alert?.entryHour, 11);
    assert.equal(alert?.baseHour, 10);
    assert.equal(alert?.symbolH1Signal, direction === "T" ? "BUY" : "SELL");
  }
});

test("H9 SW entry H11 waits for same-day H10 close before publishing XAU signal", () => {
  const date = "2026-09-08";
  const snapshot = market(date, "TGGTTT", "ALT");
  snapshot.XAUUSD.bars = snapshot.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + 6 }));
  const pending = evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [9], 9)[0];
  assert.deepEqual([pending?.slotHour, pending?.entryHour, pending?.baseHour, pending?.baseDirection, pending?.symbolH1Signal], [9, 11, 10, "", null]);
  setOwnSignalHour(snapshot, "XAUUSD", date, 10, "G");
  const ready = evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [9], 11)[0];
  assert.deepEqual([ready?.slotHour, ready?.entryHour, ready?.baseHour, ready?.baseDirection, ready?.symbolH1Signal], [9, 11, 10, "G", "SELL"]);
});

test("H16 calculates pattern entry time for every row but never computes a signal", () => {
  const date = "2026-09-02";
  const shift = 13;
  const snapshot = market(date, "TTGTTT", "ALT");
  snapshot.XAUUSD.bars = snapshot.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + shift }));

  for (const base of H1_TARGET_BASES) {
    const alert = evaluateLocalH1PatternsForTarget(base, date, snapshot, [16], 16)[0];
    assert.equal(alert?.slotHour, 16);
    assert.equal(alert?.entryHour, 17);
    assert.equal(alert?.patternGroup, "BT");
    assert.equal(alert?.baseH1Signal, null);
    assert.equal(alert?.baseDirection, "");
    assert.equal(alert?.symbolH1Signal, null);
  }
});

test("Monday calculates every row on every block with shared XAU entry and independent own-candle signals", () => {
  const monday = "2026-09-07";
  for (const slotHour of H1_SCAN_HOURS) {
    const shift = slotHour - 3;
    const snapshot = market(monday, "TTGTTT", "ALT");
    snapshot.XAUUSD.bars = snapshot.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + shift }));
    for (const target of H1_TARGET_BASES) {
      setOwnSignalHour(snapshot, target, monday, slotHour, target === "GBPUSD" ? "G" : "T");
      const alert = evaluateLocalH1PatternsForTarget(target, monday, snapshot, [slotHour], slotHour + 1)[0];
      assert.equal(alert?.entryHour, slotHour + 1);
      assert.equal(alert?.scannerSource, "XAUUSD");
      assert.equal(alert?.baseSymbol, target);
      assert.equal(alert?.baseHour, slotHour);
      assert.equal(alert?.symbolH1Signal, slotHour === 16 ? null : target === "GBPUSD" ? "SELL" : "BUY");
    }
  }
  assert.equal(scheduledSignalSlotForVietnamWall("GBPUSD", monday, 9, 5), 3);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPAUD", monday, 15, 5), 9);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPCAD", monday, 15, 5), 9);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPJPY", monday, 15, 5), 9);
});

test("timed Telegram signal mapping still stops at H14 because H16 is entry-only", () => {
  const date = "2026-09-02";
  assert.equal(h1TargetBaseFromSymbol("xauusd+"), "XAUUSD");
  assert.equal(h1TargetBaseFromSymbol("GBPCAD.a"), "GBPCAD");
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 9, 5), 3);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 10, 5), 3);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 12, 5), 6);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPUSD", date, 9, 5), 3);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPUSD", date, 12, 5), 6);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPUSD", date, 15, 5), 9);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPCAD", date, 9, 5), 3);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPCAD", date, 12, 5), 6);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPCAD", date, 15, 5), 9);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPJPY", date, 9, 5), 3);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPJPY", date, 12, 5), 6);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 20, 5), 14);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 22, 4), 14);
  assert.equal(scheduledSignalSlotForBrokerHour("XAUUSD", date, 16), 14);
  assert.equal(scheduledSignalSlotForBrokerHour("GBPCAD", date, 16), 14);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 22, 5), null);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 23, 0), null);
});

test("cloud state v56 round-trips the v86 XAU-entry own-candle contract", () => {
  const date = "2026-09-08";
  const state = emptyCloudState();
  const snapshot = market(date, "TTGTTT", "ALT");
  setOwnSignalHour(snapshot, "GBPAUD", date, 3, "G");
  const alert = evaluateLocalH1PatternsForTarget("GBPAUD", date, snapshot, [3], 4)[0];
  ensureSymbolDay(state, date, "GBPAUD").symbol.alerts.push(alert);
  const parsed = parseCloudState(JSON.stringify(state));
  const stored = parsed.days[date].symbols.GBPAUD?.alerts[0];
  assert.equal(stored?.entryHour, 4);
  assert.equal(stored?.patternGroup, "BT");
  assert.equal(stored?.scannerSource, "XAUUSD");
  assert.equal(stored?.baseSymbol, "GBPAUD");
  assert.equal(stored?.baseHour, 3);
  assert.deepEqual([stored?.baseH1Signal, stored?.symbolH1Signal, stored?.inversionBadge], ["SELL", "SELL", false]);
  assert.throws(() => parseCloudState({ version: 55, days: {} }), /schema/i);
});

test("v86 retains valid Monday rows for all five symbols in cloud state and public feed", () => {
  const monday = "2026-09-07";
  const state = emptyCloudState();
  const snapshot = market(monday, "TTGTTT", "ALT");
  for (const base of H1_TARGET_BASES) {
    setOwnSignalHour(snapshot, base, monday, 3, base === "GBPUSD" ? "G" : "T");
    const alert = evaluateLocalH1PatternsForTarget(base, monday, snapshot, [3], 4)[0];
    ensureSymbolDay(state, monday, base).symbol.alerts.push(alert);
  }

  const reparsed = parseCloudState(JSON.stringify(state));
  const feed = buildPublicFeed(state, "2026-09-07T12:00:00.000Z");
  for (const base of H1_TARGET_BASES) {
    assert.equal(reparsed.days[monday].symbols[base]?.alerts.length, 1);
    assert.equal(feed.days[monday].symbols[base]?.alerts.length, 1);
  }
  assert.deepEqual(feed.symbols, ["XAUUSD", "GBPUSD", "GBPAUD", "GBPCAD", "GBPJPY"]);
});

test("v86 never relabels retained v85 local-pattern rows before source-candle backfill", () => {
  const date = "2026-09-08";
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push({
    slotHour: 3, symbol: "XAUUSD", profile: H1_CLOUD_PROFILE, baseSymbol: "GBPUSD",
    baseH1Signal: "BUY", baseHour: 2, baseMinute: 0, baseDirection: "T", symbolH1Signal: "BUY",
    scheduledSignal: null, postSignalInverted: false, postSignalRule: "none", entryHour: 4,
    patternGroup: "BT", patternFamily: "ALT", pattern: "TTG", scannerSource: "XAUUSD", inversionBadge: false, sampleBars: [],
  });
  assert.deepEqual(parseCloudState(JSON.stringify(state)).days[date].symbols.XAUUSD?.alerts, []);
  assert.deepEqual(buildPublicFeed(state).days[date].symbols.XAUUSD?.alerts, []);
});

test("public feed keeps H16 entry metadata but sanitizes every computed signal field", () => {
  const date = "2026-09-02";
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push({
    slotHour: 16, symbol: "XAUUSD", profile: H1_CLOUD_PROFILE, baseSymbol: "XAUUSD",
    baseH1Signal: "BUY", baseHour: 17, baseMinute: 0, baseDirection: "T", symbolH1Signal: "BUY",
    scheduledSignal: "SELL", postSignalInverted: false, postSignalRule: "none", entryHour: 18,
    patternGroup: "SW", patternFamily: "ALT", pattern: "TGG", scannerSource: "XAUUSD", inversionBadge: false, sampleBars: [],
  });
  const feed = buildPublicFeed(state, "2026-09-02T01:00:00.000Z");
  assert.deepEqual(feed.hours, [3, 6, 9, 12, 14, 16]);
  const h16 = feed.days[date].symbols.XAUUSD?.alerts.find((row) => row.slotHour === 16);
  assert.deepEqual([h16?.entryHour, h16?.patternGroup, h16?.signal, h16?.scheduledSignal, h16?.baseSignal, h16?.baseDirection], [18, "SW", null, null, null, ""]);
});

test("rule bumps keep H1 history on a schema-stable state key and retain legacy migration keys", () => {
  assert.equal(H1_CLOUD_STATE_KEY, `robot-sltp:cloud:h1-scanner:state:s${H1_CLOUD_STATE_VERSION}`);
  assert.deepEqual(H1_LEGACY_CLOUD_STATE_KEYS, [
    "robot-sltp:cloud:h1-scanner:state:v73",
    "robot-sltp:cloud:h1-scanner:state:v72",
  ]);
});

test("legacy history merges under v86 and preserves H16 entry metadata without stale signals", () => {
  const oldDate = "2026-09-02";
  const currentDate = "2026-09-03";
  const legacy = emptyCloudState();
  legacy.days[oldDate] = { symbols: {} };
  const oldDay = legacy.days[oldDate];
  oldDay.symbols.XAUUSD = { alerts: [
    {
      slotHour: 3, symbol: "XAUUSD", profile: H1_CLOUD_PROFILE, baseSymbol: "XAUUSD",
      baseH1Signal: "BUY", baseHour: 4, baseMinute: 0, baseDirection: "T", symbolH1Signal: "BUY",
      scheduledSignal: null, postSignalInverted: false, postSignalRule: "none", entryHour: 5,
      patternGroup: "BT", patternFamily: "ALT", pattern: "TTGTTT", scannerSource: "XAUUSD", inversionBadge: false, sampleBars: [],
    },
    {
      slotHour: 14, symbol: "XAUUSD", profile: H1_CLOUD_PROFILE, baseSymbol: "XAUUSD",
      baseH1Signal: "SELL", baseHour: 15, baseMinute: 0, baseDirection: "G", symbolH1Signal: "SELL",
      scheduledSignal: null, postSignalInverted: false, postSignalRule: "none", entryHour: 16,
      patternGroup: "BT", patternFamily: "ALT", pattern: "TTGTTT", scannerSource: "XAUUSD", inversionBadge: false, sampleBars: [],
    },
    {
      slotHour: 16, symbol: "XAUUSD", profile: H1_CLOUD_PROFILE, baseSymbol: "XAUUSD",
      baseH1Signal: "BUY", baseHour: 17, baseMinute: 0, baseDirection: "T", symbolH1Signal: null,
      scheduledSignal: null, postSignalInverted: false, postSignalRule: "none", entryHour: 18,
      patternGroup: "BT", patternFamily: "ALT", pattern: "TTGTTT", scannerSource: "XAUUSD", inversionBadge: false, sampleBars: [],
    },
  ] };
  oldDay.symbols.GBPUSD = { alerts: [
    {
      slotHour: 14, symbol: "GBPUSD", profile: H1_CLOUD_PROFILE, baseSymbol: "GBPUSD",
      baseH1Signal: "SELL", baseHour: 15, baseMinute: 0, baseDirection: "G", symbolH1Signal: "SELL",
      scheduledSignal: null, postSignalInverted: false, postSignalRule: "none", entryHour: 16,
      patternGroup: "BT", patternFamily: "ALT", pattern: "TTGTTT", scannerSource: "XAUUSD", inversionBadge: false, sampleBars: [],
    },
    {
      slotHour: 16, symbol: "GBPUSD", profile: H1_CLOUD_PROFILE, baseSymbol: "GBPUSD",
      baseH1Signal: "BUY", baseHour: 17, baseMinute: 0, baseDirection: "T", symbolH1Signal: null,
      scheduledSignal: null, postSignalInverted: false, postSignalRule: "none", entryHour: 18,
      patternGroup: "BT", patternFamily: "ALT", pattern: "TTGTTT", scannerSource: "XAUUSD", inversionBadge: false, sampleBars: [],
    },
  ] };
  oldDay.symbols.GBPAUD = { alerts: [
    {
      slotHour: 14, symbol: "GBPAUD", profile: H1_CLOUD_PROFILE, baseSymbol: "GBPAUD",
      baseH1Signal: "BUY", baseHour: 15, baseMinute: 0, baseDirection: "T", symbolH1Signal: "BUY",
      scheduledSignal: null, postSignalInverted: false, postSignalRule: "none", entryHour: 16,
      patternGroup: "BT", patternFamily: "ALT", pattern: "TTGTTT", scannerSource: "XAUUSD", inversionBadge: false, sampleBars: [],
    },
    {
      slotHour: 16, symbol: "GBPAUD", profile: H1_CLOUD_PROFILE, baseSymbol: "GBPAUD",
      baseH1Signal: "SELL", baseHour: 17, baseMinute: 0, baseDirection: "G", symbolH1Signal: null,
      scheduledSignal: null, postSignalInverted: false, postSignalRule: "none", entryHour: 18,
      patternGroup: "BT", patternFamily: "ALT", pattern: "TTGTTT", scannerSource: "XAUUSD", inversionBadge: false, sampleBars: [],
    },
  ] };

  const reparsed = parseCloudState(JSON.stringify(legacy));
  for (const base of ["XAUUSD", "GBPUSD", "GBPAUD"] as const) {
    const h16 = reparsed.days[oldDate].symbols[base]?.alerts.find((row) => row.slotHour === 16);
    assert.equal(h16?.entryHour, 18);
    assert.deepEqual([h16?.baseH1Signal, h16?.baseDirection, h16?.symbolH1Signal], [null, "", null]);
  }

  const current = emptyCloudState();
  current.days[currentDate] = { symbols: { XAUUSD: { alerts: [] } } };
  const merged = mergeH1CloudStateHistory(reparsed, current);
  assert.deepEqual(Object.keys(merged.days).sort(), [oldDate, currentDate]);
  assert.equal(merged.days[currentDate], current.days[currentDate]);
});

test("public feed schema 18 exposes v86 shared entry plus own-symbol BUY/SELL and can seed state", () => {
  const date = "2026-09-08";
  const state = emptyCloudState();
  const snapshot = market(date, "TTGTTT", "ALT");
  setOwnSignalHour(snapshot, "GBPAUD", date, 3, "T");
  const alert = evaluateLocalH1PatternsForTarget("GBPAUD", date, snapshot, [3], 4)[0];
  ensureSymbolDay(state, date, "GBPAUD").symbol.alerts.push(alert);
  const feed = buildPublicFeed(state, "2026-09-08T01:00:00.000Z");
  assert.deepEqual([feed.schemaVersion, feed.signalRuleVersion, feed.hours], [18, 86, [3, 6, 9, 12, 14, 16]]);
  const row = feed.days[date].symbols.GBPAUD?.alerts[0];
  assert.deepEqual([row?.entryHour, row?.patternGroup, row?.scannerSource, row?.baseSymbol, row?.baseSignal, row?.signal, row?.inversionBadge], [4, "BT", "XAUUSD", "GBPAUD", "BUY", "BUY", false]);
  assert.equal(row?.sampleBars.length, 5);
  const seeded = parsePublicFeedCloudState(feed);
  const seededAlert = seeded?.days[date].symbols.GBPAUD?.alerts[0];
  assert.deepEqual([seededAlert?.entryHour, seededAlert?.baseSymbol, seededAlert?.baseH1Signal, seededAlert?.symbolH1Signal], [4, "GBPAUD", "BUY", "BUY"]);
  assert.equal(seededAlert?.sampleBars?.length, 5);
});
