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

test("rule v84 uses local MT5 ICMarkets, schema 18 and six blocks with H16 entry-only", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 56);
  assert.equal(H1_PUBLIC_SCHEMA, 18);
  assert.equal(H1_SIGNAL_RULE_VERSION, 84);
  assert.equal(H1_CLOUD_PROFILE, "MT5 ICMarkets Local");
  assert.equal(H1_SCAN_END_HOUR, 16);
  assert.equal(H1_SIGNAL_END_HOUR, 14);
  assert.deepEqual(H1_SCAN_HOURS, [3, 6, 9, 12, 14, 16]);
  assert.deepEqual(H1_TARGET_BASES, ["XAUUSD", "GBPUSD", "EURUSD", "GBPAUD", "GBPCAD", "GBPJPY"]);
});

test("GBPCAD and GBPJPY use the same block eligibility as GBPAUD and H16 is restored", () => {
  const crossBlocks = ["XAUUSD", "GBPAUD", "GBPCAD", "GBPJPY"];
  assert.deepEqual(targetsForBlockHour(3), crossBlocks);
  assert.deepEqual(targetsForBlockHour(6), crossBlocks);
  assert.deepEqual(targetsForBlockHour(9), [...H1_TARGET_BASES]);
  assert.deepEqual(targetsForBlockHour(12), [...H1_TARGET_BASES]);
  assert.deepEqual(targetsForBlockHour(14), [...H1_TARGET_BASES]);
  assert.deepEqual(targetsForBlockHour(16), [...H1_TARGET_BASES]);
  assert.deepEqual(targetsForBlockHour(4), []);
});

test("GBPAUD pattern timing comes from AUDUSD while final base comes from GBPUSD H(entry-2)", () => {
  const date = "2026-09-02";
  const snapshot = market(date, "TTGTTT", "ALT");
  snapshot.GBPUSD.bars = [...snapshot.GBPUSD.bars, ...h1Bars("2026-09-01", 2, "T")];
  const alerts = evaluateLocalH1PatternsForTarget("GBPAUD", date, snapshot, [3], 3);
  assert.equal(alerts.length, 1);
  assert.deepEqual(
    [alerts[0].slotHour, alerts[0].entryHour, alerts[0].patternGroup, alerts[0].scannerSource],
    [3, 4, "BT", "AUDUSD"],
  );
  assert.deepEqual(
    [alerts[0].baseSymbol, alerts[0].baseHour, alerts[0].baseDirection, alerts[0].baseH1Signal, alerts[0].symbolH1Signal],
    ["GBPUSD", 2, "T", "BUY", "BUY"],
  );
  assert.equal(alerts[0].inversionBadge, false);
  assert.equal(alerts[0].sampleBars?.length, 6);
  assert.equal(alerts[0].sampleBars?.[0].brokerTime, "02:15");
});

test("Tuesday GBPAUD uses AUDUSD scanner and GBPUSD H(entry-2) signal base", () => {
  const date = "2026-09-08";
  const snapshot = market(date, "TTGTTT", "ALT");
  snapshot.GBPUSD.bars = [...snapshot.GBPUSD.bars, ...h1Bars("2026-09-07", 2, "G")];
  const alert = evaluateLocalH1PatternsForTarget("GBPAUD", date, snapshot, [3], 3)[0];
  assert.equal(alert?.scannerSource, "AUDUSD");
  assert.equal(alert?.baseSymbol, "GBPUSD");
  assert.equal(alert?.baseH1Signal, "SELL");
  assert.equal(alert?.symbolH1Signal, "SELL");
  assert.equal(alert?.inversionBadge, false);
});

test("XAUUSD uses previous broker day GBPUSD H(entry-2) for BT and SW entries", () => {
  const date = "2026-09-02";

  const bt = market(date, "TTGTTT", "ALT");
  bt.XAUUSD.bars = bt.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + 3 }));
  bt.GBPUSD.bars = [...h1Bars("2026-08-31", 5, "G"), ...h1Bars("2026-09-01", 5, "T")];
  const btAlert = evaluateLocalH1PatternsForTarget("XAUUSD", date, bt, [6], 6)[0];
  assert.deepEqual([btAlert?.entryHour, btAlert?.baseHour, btAlert?.baseDirection, btAlert?.baseH1Signal, btAlert?.symbolH1Signal], [7, 5, "T", "BUY", "BUY"]);

  const sw = market(date, "TGGTTT", "ALT");
  sw.XAUUSD.bars = sw.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + 3 }));
  sw.GBPUSD.bars = [...h1Bars("2026-08-31", 6, "G"), ...h1Bars("2026-09-01", 6, "T")];
  const swAlert = evaluateLocalH1PatternsForTarget("XAUUSD", date, sw, [6], 6)[0];
  assert.deepEqual([swAlert?.entryHour, swAlert?.baseHour, swAlert?.baseDirection, swAlert?.baseH1Signal, swAlert?.symbolH1Signal], [8, 6, "T", "BUY", "BUY"]);
});

test("GBPUSD and EURUSD copy XAUUSD entry time and final side on H9/H12/H14", () => {
  for (const [date, previousDate] of [
    ["2026-09-02", "2026-09-01"],
    ["2026-09-03", "2026-09-02"],
    ["2026-09-04", "2026-09-03"],
  ] as const) {
    for (const slotHour of [9, 12, 14] as const) {
      const snapshot = market(date, "TGGTTT", "ALT");
      const shift = slotHour - 3;
      snapshot.XAUUSD.bars = snapshot.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + shift }));
      snapshot.GBPUSD.bars = bars(date, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
      snapshot.EURUSD.bars = bars(date, "TGGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
      snapshot.GBPUSD.bars = [
        ...snapshot.GBPUSD.bars,
        ...h1Bars(previousDate, slotHour - 1, "G"),
        ...h1Bars(previousDate, slotHour, "T"),
        ...h1Bars(previousDate, slotHour + 1, "T"),
      ];
      snapshot.USDCAD.bars = bars(date, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
      const xau = evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [slotHour], slotHour)[0];
      const cad = evaluateLocalH1PatternsForTarget("GBPCAD", date, snapshot, [slotHour], slotHour)[0];
      const gbp = evaluateLocalH1PatternsForTarget("GBPUSD", date, snapshot, [slotHour], slotHour)[0];
      const eur = evaluateLocalH1PatternsForTarget("EURUSD", date, snapshot, [slotHour], slotHour)[0];
      assert.equal(xau?.entryHour, slotHour + 2);
      assert.equal(xau?.baseHour, slotHour);
      assert.equal(xau?.symbolH1Signal, "BUY");
      assert.equal(cad?.entryHour, slotHour + 1);
      assert.equal(cad?.scannerSource, "USDCAD");
      assert.equal(cad?.baseSymbol, "GBPUSD");
      assert.equal(cad?.baseHour, slotHour - 1);
      assert.equal(cad?.symbolH1Signal, "SELL");
      assert.equal(gbp?.entryHour, xau?.entryHour);
      assert.equal(eur?.entryHour, xau?.entryHour);
      assert.equal(gbp?.symbolH1Signal, xau?.symbolH1Signal);
      assert.equal(eur?.symbolH1Signal, xau?.symbolH1Signal);
      assert.equal(gbp?.scannerSource, "GBPUSD");
      assert.equal(eur?.scannerSource, "GBPUSD");
    }
  }
});

test("all three GBP crosses calculate every block like GBPAUD with dedicated scanners", () => {
  const date = "2026-09-02";
  const configs = [
    ["GBPAUD", "AUDUSD"],
    ["GBPCAD", "USDCAD"],
    ["GBPJPY", "USDJPY"],
  ] as const;

  for (const slotHour of H1_SCAN_HOURS) {
    const shift = slotHour - 3;
    const snapshot = market(date, "TTGTTT", "ALT");
    snapshot.AUDUSD.bars = bars(date, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
    snapshot.USDCAD.bars = bars(date, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
    snapshot.USDJPY.bars = bars(date, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
    snapshot.GBPUSD.bars = [...snapshot.GBPUSD.bars, ...h1Bars("2026-09-01", slotHour - 1, "T")];

    for (const [target, scannerSource] of configs) {
      const alert = evaluateLocalH1PatternsForTarget(target, date, snapshot, [slotHour], slotHour)[0];
      assert.equal(alert?.entryHour, slotHour + 1);
      assert.equal(alert?.scannerSource, scannerSource);
      assert.equal(alert?.baseSymbol, "GBPUSD");
      assert.equal(alert?.baseHour, slotHour - 1);
      assert.equal(alert?.symbolH1Signal, slotHour === 16 ? null : "BUY");
      if (slotHour === 16) assert.deepEqual([alert?.baseH1Signal, alert?.baseDirection], [null, ""]);
    }
  }
});

test("dedicated GBP-cross scanners can produce different entry hours in the same block", () => {
  const date = "2026-09-02";
  const previousDate = "2026-09-01";
  const slotHour = 9;
  const shift = slotHour - 3;
  const snapshot = market(date, "TTGTTT", "ALT");
  snapshot.AUDUSD.bars = bars(date, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
  snapshot.USDCAD.bars = bars(date, "TGGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
  snapshot.USDJPY.bars = bars(date, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
  snapshot.GBPUSD.bars = [
    ...snapshot.GBPUSD.bars,
    ...h1Bars(previousDate, 8, "T"),
    ...h1Bars(previousDate, 9, "G"),
  ];

  const aud = evaluateLocalH1PatternsForTarget("GBPAUD", date, snapshot, [slotHour], slotHour)[0];
  const cad = evaluateLocalH1PatternsForTarget("GBPCAD", date, snapshot, [slotHour], slotHour)[0];
  const jpy = evaluateLocalH1PatternsForTarget("GBPJPY", date, snapshot, [slotHour], slotHour)[0];

  assert.deepEqual([aud?.scannerSource, aud?.entryHour, aud?.baseSymbol, aud?.baseHour, aud?.symbolH1Signal], ["AUDUSD", 10, "GBPUSD", 8, "BUY"]);
  assert.deepEqual([cad?.scannerSource, cad?.entryHour, cad?.baseSymbol, cad?.baseHour, cad?.symbolH1Signal], ["USDCAD", 11, "GBPUSD", 9, "SELL"]);
  assert.deepEqual([jpy?.scannerSource, jpy?.entryHour, jpy?.baseSymbol, jpy?.baseHour, jpy?.symbolH1Signal], ["USDJPY", 10, "GBPUSD", 8, "BUY"]);
});

test("H9 can publish an H11 XAU signal immediately from previous broker day GBPUSD H9", () => {
  const date = "2026-09-02";
  const snapshot = market(date, "TGGTTT", "ALT");
  snapshot.XAUUSD.bars = snapshot.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + 6 }));
  snapshot.GBPUSD.bars = h1Bars("2026-09-01", 9, "G");
  const alert = evaluateLocalH1PatternsForTarget("XAUUSD", date, snapshot, [9], 9)[0];
  assert.deepEqual([alert?.slotHour, alert?.entryHour, alert?.baseHour, alert?.baseDirection, alert?.symbolH1Signal], [9, 11, 9, "G", "SELL"]);
});

test("H16 calculates pattern entry time for every row but never computes a signal", () => {
  const date = "2026-09-02";
  const shift = 13;
  const snapshot = market(date, "TTGTTT", "ALT");
  snapshot.XAUUSD.bars = snapshot.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + shift }));
  snapshot.GBPUSD.bars = bars(date, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
  snapshot.EURUSD.bars = bars(date, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
  snapshot.AUDUSD.bars = bars(date, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
  snapshot.USDCAD.bars = bars(date, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
  snapshot.USDJPY.bars = bars(date, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));

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

test("Monday evaluates dedicated FX scanners with GBPUSD signal bases like normal weekdays", () => {
  const monday = "2026-09-07";
  const previousFriday = "2026-09-04";
  const configs = [
    ["GBPUSD", "GBPUSD", [9, 12, 14, 16]],
    ["EURUSD", "GBPUSD", [9, 12, 14, 16]],
    ["GBPAUD", "AUDUSD", [3, 6, 9, 12, 14, 16]],
    ["GBPCAD", "USDCAD", [3, 6, 9, 12, 14, 16]],
    ["GBPJPY", "USDJPY", [3, 6, 9, 12, 14, 16]],
  ] as const;

  for (const slotHour of H1_SCAN_HOURS) {
    const shift = slotHour - 3;
    const snapshot = market(monday, "TTGTTT", "ALT");
    snapshot.XAUUSD.bars = snapshot.XAUUSD.bars.map((row) => ({ ...row, hour: row.hour + shift }));
    snapshot.GBPUSD.bars = [
      ...bars(monday, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift })),
      ...h1Bars(previousFriday, slotHour - 1, "T"),
      ...h1Bars(previousFriday, slotHour, "T"),
    ];
    snapshot.EURUSD.bars = bars(monday, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
    snapshot.AUDUSD.bars = bars(monday, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
    snapshot.USDCAD.bars = bars(monday, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));
    snapshot.USDJPY.bars = bars(monday, "TTGTTT", "ALT").map((row) => ({ ...row, hour: row.hour + shift }));

    for (const [target, scannerSource, eligibleHours] of configs) {
      const alert = evaluateLocalH1PatternsForTarget(target, monday, snapshot, [slotHour], slotHour)[0];
      if (!(eligibleHours as readonly number[]).includes(slotHour)) {
        assert.equal(alert, undefined);
        continue;
      }
      assert.equal(alert?.entryHour, slotHour + 1);
      assert.equal(alert?.scannerSource, target === "EURUSD" && slotHour === 16 ? "EURUSD" : scannerSource);
      assert.equal(alert?.baseSymbol, "GBPUSD");
      assert.equal(alert?.baseHour, target === "GBPUSD" || target === "EURUSD" ? slotHour : slotHour - 1);
      assert.equal(alert?.symbolH1Signal, slotHour === 16 ? null : "BUY");
    }
  }
});

test("timed Telegram signal mapping still stops at H14 because H16 is entry-only", () => {
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

test("cloud state v56 round-trips the v84 GBP-cross scanner/base contract", () => {
  const date = "2026-09-02";
  const state = emptyCloudState();
  const snapshot = market(date, "TTGTTT", "ALT");
  snapshot.GBPUSD.bars = [...snapshot.GBPUSD.bars, ...h1Bars("2026-09-01", 2, "G")];
  const alert = evaluateLocalH1PatternsForTarget("GBPAUD", date, snapshot, [3], 3)[0];
  ensureSymbolDay(state, date, "GBPAUD").symbol.alerts.push(alert);
  const parsed = parseCloudState(JSON.stringify(state));
  const stored = parsed.days[date].symbols.GBPAUD?.alerts[0];
  assert.equal(stored?.entryHour, 4);
  assert.equal(stored?.patternGroup, "BT");
  assert.equal(stored?.scannerSource, "AUDUSD");
  assert.equal(stored?.baseSymbol, "GBPUSD");
  assert.deepEqual([stored?.baseH1Signal, stored?.symbolH1Signal, stored?.inversionBadge], ["SELL", "SELL", false]);
  assert.throws(() => parseCloudState({ version: 55, days: {} }), /schema/i);
});

test("public feed keeps H16 entry metadata but sanitizes every computed signal field", () => {
  const date = "2026-09-02";
  const state = emptyCloudState();
  ensureSymbolDay(state, date, "XAUUSD").symbol.alerts.push({
    slotHour: 16, symbol: "XAUUSD", profile: H1_CLOUD_PROFILE, baseSymbol: "GBPUSD",
    baseH1Signal: "BUY", baseHour: 16, baseMinute: 0, baseDirection: "T", symbolH1Signal: "BUY",
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

test("legacy history merges under v84 and preserves H16 entry metadata without stale signals", () => {
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

test("public feed schema 18 exposes entry time plus final BUY/SELL and can seed state", () => {
  const date = "2026-09-02";
  const state = emptyCloudState();
  const snapshot = market(date, "TTGTTT", "ALT");
  snapshot.GBPUSD.bars = [...snapshot.GBPUSD.bars, ...h1Bars("2026-09-01", 2, "T")];
  const alert = evaluateLocalH1PatternsForTarget("GBPAUD", date, snapshot, [3], 3)[0];
  ensureSymbolDay(state, date, "GBPAUD").symbol.alerts.push(alert);
  const feed = buildPublicFeed(state, "2026-09-02T01:00:00.000Z");
  assert.deepEqual([feed.schemaVersion, feed.signalRuleVersion, feed.hours], [18, 84, [3, 6, 9, 12, 14, 16]]);
  const row = feed.days[date].symbols.GBPAUD?.alerts[0];
  assert.deepEqual([row?.entryHour, row?.patternGroup, row?.scannerSource, row?.baseSymbol, row?.baseSignal, row?.signal, row?.inversionBadge], [4, "BT", "AUDUSD", "GBPUSD", "BUY", "BUY", false]);
  assert.equal(row?.sampleBars.length, 6);
  assert.equal(row?.sampleBars[0]?.open, 202);
  const seeded = parsePublicFeedCloudState(feed);
  const seededAlert = seeded?.days[date].symbols.GBPAUD?.alerts[0];
  assert.deepEqual([seededAlert?.entryHour, seededAlert?.baseSymbol, seededAlert?.baseH1Signal, seededAlert?.symbolH1Signal], [4, "GBPUSD", "BUY", "BUY"]);
  assert.equal(seededAlert?.sampleBars?.length, 6);
});
