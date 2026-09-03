import assert from "node:assert/strict";
import test from "node:test";

import {
  H1_CLOUD_PROFILE,
  H1_CLOUD_STATE_KEY,
  H1_CLOUD_STATE_VERSION,
  H1_LEGACY_CLOUD_STATE_KEYS,
  H1_PUBLIC_SCHEMA,
  H1_SCAN_HOURS,
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
  repairLegacyH16AdvisorySignals,
  scheduledSignalSlotForVietnamWall,
  targetsForBlockHour,
  xauH3EntryHour,
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
    AUDUSD: { displayName: "AUDUSD", bars: sourceBars },
    USDCAD: { displayName: "USDCAD", bars: sourceBars },
    USDJPY: { displayName: "USDJPY", bars: sourceBars },
    GBPUSD: { displayName: "GBPUSD", bars: sourceBars },
    EURUSD: { displayName: "EURUSD", bars: sourceBars },
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

test("rule v74 uses local MT5 ICMarkets, schema 18 and six blocks", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 56);
  assert.equal(H1_PUBLIC_SCHEMA, 18);
  assert.equal(H1_SIGNAL_RULE_VERSION, 74);
  assert.equal(H1_CLOUD_PROFILE, "MT5 ICMarkets Local");
  assert.deepEqual(H1_SCAN_HOURS, [3, 6, 9, 12, 14, 16]);
  assert.deepEqual(H1_TARGET_BASES, ["XAUUSD", "GBPUSD", "EURUSD", "GBPAUD", "GBPCAD", "GBPJPY"]);
});

test("early blocks expose only eligible H1 rows", () => {
  assert.deepEqual(targetsForBlockHour(3), ["XAUUSD", "GBPAUD"]);
  assert.deepEqual(targetsForBlockHour(6), ["XAUUSD", "GBPAUD", "GBPJPY"]);
  for (const hour of [9, 12, 14, 16]) assert.deepEqual(targetsForBlockHour(hour), [...H1_TARGET_BASES]);
  assert.deepEqual(targetsForBlockHour(4), []);
});

test("GBP cross pattern timing comes from GBPUSD while GBPAUD signal base comes from AUDUSD", () => {
  const date = "2026-09-02";
  const snapshot = market(date, "TTGTTT", "ALT");
  snapshot.AUDUSD.bars = [...snapshot.AUDUSD.bars, ...h1Bars("2026-09-01", 3, "T")];
  const alerts = evaluateLocalH1PatternsForTarget("GBPAUD", date, snapshot, [3], 3);
  assert.equal(alerts.length, 1);
  assert.deepEqual(
    [alerts[0].slotHour, alerts[0].entryHour, alerts[0].patternGroup, alerts[0].scannerSource],
    [3, 4, "BT", "GBPUSD"],
  );
  assert.deepEqual(
    [alerts[0].baseSymbol, alerts[0].baseHour, alerts[0].baseDirection, alerts[0].baseH1Signal, alerts[0].symbolH1Signal],
    ["AUDUSD", 3, "T", "BUY", "BUY"],
  );
  assert.equal(alerts[0].inversionBadge, false);
  assert.equal(alerts[0].sampleBars?.length, 6);
  assert.equal(alerts[0].sampleBars?.[0].brokerTime, "02:15");
});

test("Tuesday GBPAUD keeps the AUDUSD base side with no inversion", () => {
  const date = "2026-09-08";
  const snapshot = market(date, "TTGTTT", "ALT");
  snapshot.AUDUSD.bars = [...snapshot.AUDUSD.bars, ...h1Bars("2026-09-07", 3, "G")];
  const alert = evaluateLocalH1PatternsForTarget("GBPAUD", date, snapshot, [3], 3)[0];
  assert.equal(alert?.scannerSource, "GBPUSD");
  assert.equal(alert?.baseSymbol, "AUDUSD");
  assert.equal(alert?.baseH1Signal, "SELL");
  assert.equal(alert?.symbolH1Signal, "SELL");
  assert.equal(alert?.inversionBadge, false);
});

test("XAUUSD entry H7 uses the latest previous broker day GBPUSD H6 and keeps its direction", () => {
  const date = "2026-09-02";
  const snapshot = market(date, "TTGTTT", "ALT");
  snapshot.XAUUSD.bars = snapshot.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + 3 }));
  snapshot.GBPUSD.bars = [...h1Bars("2026-08-31", 6, "G"), ...h1Bars("2026-09-01", 6, "T")];
  const alert = evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [6], 6)[0];
  assert.deepEqual([alert?.entryHour, alert?.baseHour, alert?.baseDirection, alert?.baseH1Signal, alert?.symbolH1Signal], [7, 6, "T", "BUY", "BUY"]);
});

test("GBPUSD and EURUSD share XAUUSD entry time and final side with no weekday inversion", () => {
  for (const [date, previousDate] of [
    ["2026-09-02", "2026-09-01"],
    ["2026-09-03", "2026-09-02"],
    ["2026-09-04", "2026-09-03"],
  ] as const) {
    for (const slotHour of [9, 12, 14, 16] as const) {
      const snapshot = market(date, "TGGTTT", "ALT");
      const shift = slotHour - 3;
      snapshot.XAUUSD.bars = snapshot.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + shift }));
      snapshot.GBPUSD.bars = bars(date, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
      snapshot.EURUSD.bars = bars(date, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
      snapshot.GBPUSD.bars = [
        ...snapshot.GBPUSD.bars,
        ...h1Bars(previousDate, slotHour, "T"),
        ...h1Bars(previousDate, slotHour + 1, "T"),
      ];
      const xau = evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [slotHour], slotHour)[0];
      const gbp = evaluateLocalH1PatternsForTarget("GBPUSD", date, snapshot, [slotHour], slotHour)[0];
      const eur = evaluateLocalH1PatternsForTarget("EURUSD", date, snapshot, [slotHour], slotHour)[0];
      assert.equal(xau?.entryHour, slotHour + 2);
      assert.equal(gbp?.entryHour, xau?.entryHour);
      assert.equal(eur?.entryHour, xau?.entryHour);
      assert.equal(gbp?.scannerSource, "GBPUSD");
      assert.equal(eur?.scannerSource, "GBPUSD");
      assert.equal(xau?.symbolH1Signal, "BUY");
      assert.equal(gbp?.symbolH1Signal, "BUY");
      assert.equal(eur?.symbolH1Signal, "BUY");
    }
  }
});

test("GBP crosses keep GBPUSD entry timing and dedicated bases only on their eligible blocks", () => {
  const date = "2026-09-02";
  const configs = [
    ["GBPAUD", "AUDUSD", "BUY", [3, 6, 9, 12, 14, 16]],
    ["GBPCAD", "USDCAD", "SELL", [9, 12, 14, 16]],
    ["GBPJPY", "USDJPY", "BUY", [6, 9, 12, 14, 16]],
  ] as const;

  for (const slotHour of H1_SCAN_HOURS) {
    const shift = slotHour - 3;
    const snapshot = market(date, "TTGTTT", "ALT");
    snapshot.GBPUSD.bars = bars(date, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
    snapshot.AUDUSD.bars = [...snapshot.AUDUSD.bars, ...h1Bars("2026-09-01", slotHour, "T")];
    snapshot.USDCAD.bars = [...snapshot.USDCAD.bars, ...h1Bars("2026-09-01", slotHour, "G")];
    snapshot.USDJPY.bars = [...snapshot.USDJPY.bars, ...h1Bars("2026-09-01", slotHour, "T")];

    for (const [target, baseSymbol, signal, eligibleHours] of configs) {
      const alert = evaluateLocalH1PatternsForTarget(target, date, snapshot, [slotHour], slotHour)[0];
      if (!(eligibleHours as readonly number[]).includes(slotHour)) {
        assert.equal(alert, undefined);
        continue;
      }
      assert.equal(alert?.entryHour, slotHour + 1);
      assert.equal(alert?.scannerSource, "GBPUSD");
      assert.equal(alert?.baseSymbol, baseSymbol);
      if (slotHour !== 16) assert.equal(alert?.symbolH1Signal, signal);
    }
  }
});

test("H9 can publish an H11 signal immediately because its GBPUSD H10 base comes from the previous broker day", () => {
  const date = "2026-09-02";
  const snapshot = market(date, "TGGTTT", "ALT");
  snapshot.XAUUSD.bars = snapshot.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + 6 }));
  snapshot.GBPUSD.bars = h1Bars("2026-09-01", 10, "G");
  const alert = evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [9], 9)[0];
  assert.deepEqual([alert?.slotHour, alert?.entryHour, alert?.baseHour, alert?.baseDirection, alert?.symbolH1Signal], [9, 11, 10, "G", "SELL"]);
});

test("XAUUSD H3 entry H5 removes CLOSE and makes every H16 signal copy that symbol H14 signal", () => {
  const date = "2026-09-02";
  const previousDate = "2026-09-01";
  const snapshot = market(date, "TGGTTT", "ALT");
  for (const source of ["XAUUSD", "AUDUSD", "USDCAD", "USDJPY", "GBPUSD", "EURUSD"] as const) {
    const current = snapshot[source].bars.filter((row) => row.brokerDate === date);
    snapshot[source].bars = [
      ...snapshot[source].bars,
      ...current.map((row) => ({ ...row, hour: row.hour + 11 })),
      ...current.map((row) => ({ ...row, hour: row.hour + 13 })),
    ];
  }
  snapshot.GBPUSD.bars = [...snapshot.GBPUSD.bars, ...h1Bars(previousDate, 15, "G"), ...h1Bars(previousDate, 17, "T")];
  snapshot.AUDUSD.bars = [...snapshot.AUDUSD.bars, ...h1Bars(previousDate, 15, "T"), ...h1Bars(previousDate, 17, "G")];
  snapshot.USDCAD.bars = [...snapshot.USDCAD.bars, ...h1Bars(previousDate, 15, "G"), ...h1Bars(previousDate, 17, "T")];
  snapshot.USDJPY.bars = [...snapshot.USDJPY.bars, ...h1Bars(previousDate, 15, "T"), ...h1Bars(previousDate, 17, "G")];

  assert.equal(xauH3EntryHour(date, snapshot), 5);
  const expected = { XAUUSD: "SELL", GBPUSD: "SELL", EURUSD: "SELL", GBPAUD: "BUY", GBPCAD: "SELL", GBPJPY: "BUY" } as const;
  for (const base of H1_TARGET_BASES) {
    const h14 = evaluateLocalH1PatternsForTarget(base, date, snapshot, [14], 14)[0];
    const h16 = evaluateLocalH1PatternsForTarget(base, date, snapshot, [16], 16)[0];
    assert.equal(h14?.symbolH1Signal, expected[base]);
    assert.equal(h16?.symbolH1Signal, expected[base]);
    assert.equal(h16?.entryHour, 18);
  }
});

test("XAUUSD H3 entry H4 shows CLOSE and makes every H16 signal invert that symbol H14 signal", () => {
  const date = "2026-09-02";
  const previousDate = "2026-09-01";
  const snapshot = market(date, "TTGTTT", "ALT");
  for (const source of ["XAUUSD", "AUDUSD", "USDCAD", "USDJPY", "GBPUSD", "EURUSD"] as const) {
    const current = snapshot[source].bars.filter((row) => row.brokerDate === date);
    snapshot[source].bars = [
      ...snapshot[source].bars,
      ...current.map((row) => ({ ...row, hour: row.hour + 11 })),
      ...current.map((row) => ({ ...row, hour: row.hour + 13 })),
    ];
  }
  snapshot.GBPUSD.bars = [...snapshot.GBPUSD.bars, ...h1Bars(previousDate, 14, "T"), ...h1Bars(previousDate, 16, "T")];
  snapshot.AUDUSD.bars = [...snapshot.AUDUSD.bars, ...h1Bars(previousDate, 14, "G"), ...h1Bars(previousDate, 16, "G")];
  snapshot.USDCAD.bars = [...snapshot.USDCAD.bars, ...h1Bars(previousDate, 14, "T"), ...h1Bars(previousDate, 16, "T")];
  snapshot.USDJPY.bars = [...snapshot.USDJPY.bars, ...h1Bars(previousDate, 14, "G"), ...h1Bars(previousDate, 16, "G")];

  assert.equal(xauH3EntryHour(date, snapshot), 4);
  const h14Expected = { XAUUSD: "BUY", GBPUSD: "BUY", EURUSD: "BUY", GBPAUD: "SELL", GBPCAD: "BUY", GBPJPY: "SELL" } as const;
  const h16Expected = { XAUUSD: "SELL", GBPUSD: "SELL", EURUSD: "SELL", GBPAUD: "BUY", GBPCAD: "SELL", GBPJPY: "BUY" } as const;
  for (const base of H1_TARGET_BASES) {
    const h14 = evaluateLocalH1PatternsForTarget(base, date, snapshot, [14], 14)[0];
    const h16 = evaluateLocalH1PatternsForTarget(base, date, snapshot, [16], 16)[0];
    assert.equal(h14?.symbolH1Signal, h14Expected[base]);
    assert.equal(h16?.symbolH1Signal, h16Expected[base]);
    assert.equal(h16?.entryHour, 17);
  }
});

test("Monday keeps every FX row blank and remains XAUUSD-only", () => {
  const monday = "2026-09-07";
  const snapshot = market(monday, "TTGTTT", "ALT");
  for (const base of ["GBPUSD", "EURUSD", "GBPAUD", "GBPCAD", "GBPJPY"] as const) {
    assert.deepEqual(evaluateLocalH1PatternsForTarget(base, monday, snapshot, H1_SCAN_HOURS, 16), []);
  }
});

test("timed Telegram mapping follows the reopened six block set", () => {
  const date = "2026-09-02";
  assert.equal(h1TargetBaseFromSymbol("xauusd+"), "XAUUSD");
  assert.equal(h1TargetBaseFromSymbol("GBPCAD.a"), "GBPCAD");
  assert.equal(h1TargetBaseFromSymbol("EURUSD"), "EURUSD");
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 9, 5), 3);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 10, 5), 3);
  assert.equal(scheduledSignalSlotForVietnamWall("XAUUSD", date, 12, 5), 6);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPUSD", date, 9, 5), null);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPUSD", date, 12, 5), null);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPUSD", date, 15, 5), 9);
  assert.equal(scheduledSignalSlotForVietnamWall("EURUSD", date, 12, 5), null);
  assert.equal(scheduledSignalSlotForVietnamWall("EURUSD", date, 15, 5), 9);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPCAD", date, 9, 5), null);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPCAD", date, 12, 5), null);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPCAD", date, 15, 5), 9);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPJPY", date, 9, 5), null);
  assert.equal(scheduledSignalSlotForVietnamWall("GBPJPY", date, 12, 5), 6);
});

test("cloud state v56 round-trips the v74 GBP-cross scanner/base contract", () => {
  const date = "2026-09-02";
  const state = emptyCloudState();
  const snapshot = market(date, "TTGTTT", "ALT");
  snapshot.AUDUSD.bars = [...snapshot.AUDUSD.bars, ...h1Bars("2026-09-01", 3, "G")];
  const alert = evaluateLocalH1PatternsForTarget("GBPAUD", date, snapshot, [3], 3)[0];
  ensureSymbolDay(state, date, "GBPAUD").symbol.alerts.push(alert);
  const parsed = parseCloudState(JSON.stringify(state));
  const stored = parsed.days[date].symbols.GBPAUD?.alerts[0];
  assert.equal(stored?.entryHour, 4);
  assert.equal(stored?.patternGroup, "BT");
  assert.equal(stored?.scannerSource, "GBPUSD");
  assert.equal(stored?.baseSymbol, "AUDUSD");
  assert.deepEqual([stored?.baseH1Signal, stored?.symbolH1Signal, stored?.inversionBadge], ["SELL", "SELL", false]);
  assert.throws(() => parseCloudState({ version: 55, days: {} }), /schema/i);
});

test("public feed keeps GBPJPY H14/H16 entry rows while H16 copies H14 under XAU H3 entry H5", () => {
  const date = "2026-09-02";
  const previousDate = "2026-09-01";
  const state = emptyCloudState();
  const snapshot = market(date, "TGGTTT", "ALT");
  const gbpCurrent = snapshot.GBPUSD.bars.filter((row) => row.brokerDate === date);
  snapshot.GBPUSD.bars = [
    ...snapshot.GBPUSD.bars,
    ...gbpCurrent.map((row) => ({ ...row, hour: row.hour + 11 })),
    ...gbpCurrent.map((row) => ({ ...row, hour: row.hour + 13 })),
  ];
  snapshot.USDJPY.bars = [
    ...snapshot.USDJPY.bars,
    ...h1Bars(previousDate, 15, "T"),
    ...h1Bars(previousDate, 17, "G"),
  ];
  for (const slotHour of [14, 16] as const) {
    const alert = evaluateLocalH1PatternsForTarget("GBPJPY", date, snapshot, [slotHour], slotHour)[0];
    assert.equal(alert?.entryHour, slotHour + 2);
    assert.equal(alert?.baseSymbol, "USDJPY");
    assert.equal(alert?.scannerSource, "GBPUSD");
    assert.equal(alert?.symbolH1Signal, "BUY");
    ensureSymbolDay(state, date, "GBPJPY").symbol.alerts.push(alert);
  }

  const feed = buildPublicFeed(state, "2026-09-02T01:00:00.000Z");
  const rows = feed.days[date].symbols.GBPJPY?.alerts ?? [];
  assert.deepEqual(rows.map((row) => row.slotHour), [14, 16]);
  assert.deepEqual(rows.map((row) => [row.entryHour, row.signal]), [[16, "BUY"], [18, "BUY"]]);
});

test("rule bumps keep H1 history on a schema-stable state key and retain legacy migration keys", () => {
  assert.equal(H1_CLOUD_STATE_KEY, `robot-sltp:cloud:h1-scanner:state:s${H1_CLOUD_STATE_VERSION}`);
  assert.deepEqual(H1_LEGACY_CLOUD_STATE_KEYS, [
    "robot-sltp:cloud:h1-scanner:state:v73",
    "robot-sltp:cloud:h1-scanner:state:v72",
  ]);
});

test("legacy v72 history merges under v74 without losing dates and repairs H16 rule signals", () => {
  const oldDate = "2026-09-02";
  const currentDate = "2026-09-03";
  const legacy = emptyCloudState();
  legacy.days[oldDate] = { symbols: {} };
  const oldDay = legacy.days[oldDate];
  oldDay.symbols.XAUUSD = { alerts: [
    {
      slotHour: 3, symbol: "XAUUSD", profile: H1_CLOUD_PROFILE, baseSymbol: "GBPUSD",
      baseH1Signal: "BUY", baseHour: 4, baseMinute: 0, baseDirection: "T", symbolH1Signal: "BUY",
      scheduledSignal: null, postSignalInverted: false, postSignalRule: "none", entryHour: 5,
      patternGroup: "BT", patternFamily: "ALT", pattern: "TTGTTT", scannerSource: "XAUUSD", inversionBadge: false, sampleBars: [],
    },
    {
      slotHour: 14, symbol: "XAUUSD", profile: H1_CLOUD_PROFILE, baseSymbol: "GBPUSD",
      baseH1Signal: "SELL", baseHour: 15, baseMinute: 0, baseDirection: "G", symbolH1Signal: "SELL",
      scheduledSignal: null, postSignalInverted: false, postSignalRule: "none", entryHour: 16,
      patternGroup: "BT", patternFamily: "ALT", pattern: "TTGTTT", scannerSource: "XAUUSD", inversionBadge: false, sampleBars: [],
    },
    {
      slotHour: 16, symbol: "XAUUSD", profile: H1_CLOUD_PROFILE, baseSymbol: "GBPUSD",
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
      patternGroup: "BT", patternFamily: "ALT", pattern: "TTGTTT", scannerSource: "GBPUSD", inversionBadge: false, sampleBars: [],
    },
    {
      slotHour: 16, symbol: "GBPUSD", profile: H1_CLOUD_PROFILE, baseSymbol: "GBPUSD",
      baseH1Signal: "BUY", baseHour: 17, baseMinute: 0, baseDirection: "T", symbolH1Signal: null,
      scheduledSignal: null, postSignalInverted: false, postSignalRule: "none", entryHour: 18,
      patternGroup: "BT", patternFamily: "ALT", pattern: "TTGTTT", scannerSource: "GBPUSD", inversionBadge: false, sampleBars: [],
    },
  ] };
  oldDay.symbols.GBPAUD = { alerts: [
    {
      slotHour: 14, symbol: "GBPAUD", profile: H1_CLOUD_PROFILE, baseSymbol: "AUDUSD",
      baseH1Signal: "BUY", baseHour: 15, baseMinute: 0, baseDirection: "T", symbolH1Signal: "BUY",
      scheduledSignal: null, postSignalInverted: false, postSignalRule: "none", entryHour: 16,
      patternGroup: "BT", patternFamily: "ALT", pattern: "TTGTTT", scannerSource: "GBPUSD", inversionBadge: false, sampleBars: [],
    },
    {
      slotHour: 16, symbol: "GBPAUD", profile: H1_CLOUD_PROFILE, baseSymbol: "AUDUSD",
      baseH1Signal: "SELL", baseHour: 17, baseMinute: 0, baseDirection: "G", symbolH1Signal: null,
      scheduledSignal: null, postSignalInverted: false, postSignalRule: "none", entryHour: 18,
      patternGroup: "BT", patternFamily: "ALT", pattern: "TTGTTT", scannerSource: "GBPUSD", inversionBadge: false, sampleBars: [],
    },
  ] };

  repairLegacyH16AdvisorySignals(legacy);
  assert.equal(legacy.days[oldDate].symbols.XAUUSD?.alerts.find((row) => row.slotHour === 16)?.symbolH1Signal, "SELL");
  assert.equal(legacy.days[oldDate].symbols.GBPUSD?.alerts.find((row) => row.slotHour === 16)?.symbolH1Signal, "SELL");
  assert.equal(legacy.days[oldDate].symbols.GBPAUD?.alerts.find((row) => row.slotHour === 16)?.symbolH1Signal, "BUY");

  const current = emptyCloudState();
  current.days[currentDate] = { symbols: { XAUUSD: { alerts: [] } } };
  const merged = mergeH1CloudStateHistory(legacy, current);
  assert.deepEqual(Object.keys(merged.days).sort(), [oldDate, currentDate]);
  assert.equal(merged.days[currentDate], current.days[currentDate]);
});

test("public feed schema 18 exposes entry time plus final BUY/SELL and can seed state", () => {
  const date = "2026-09-02";
  const state = emptyCloudState();
  const snapshot = market(date, "TTGTTT", "ALT");
  snapshot.AUDUSD.bars = [...snapshot.AUDUSD.bars, ...h1Bars("2026-09-01", 3, "T")];
  const alert = evaluateLocalH1PatternsForTarget("GBPAUD", date, snapshot, [3], 3)[0];
  ensureSymbolDay(state, date, "GBPAUD").symbol.alerts.push(alert);
  const feed = buildPublicFeed(state, "2026-09-02T01:00:00.000Z");
  assert.deepEqual([feed.schemaVersion, feed.signalRuleVersion, feed.hours], [18, 74, [3, 6, 9, 12, 14, 16]]);
  const row = feed.days[date].symbols.GBPAUD?.alerts[0];
  assert.deepEqual([row?.entryHour, row?.patternGroup, row?.scannerSource, row?.baseSymbol, row?.baseSignal, row?.signal, row?.inversionBadge], [4, "BT", "GBPUSD", "AUDUSD", "BUY", "BUY", false]);
  assert.equal(row?.sampleBars.length, 6);
  assert.equal(row?.sampleBars[0]?.open, 202);
  const seeded = parsePublicFeedCloudState(feed);
  const seededAlert = seeded?.days[date].symbols.GBPAUD?.alerts[0];
  assert.deepEqual([seededAlert?.entryHour, seededAlert?.baseSymbol, seededAlert?.baseH1Signal, seededAlert?.symbolH1Signal], [4, "AUDUSD", "BUY", "BUY"]);
  assert.equal(seededAlert?.sampleBars?.length, 6);
});
