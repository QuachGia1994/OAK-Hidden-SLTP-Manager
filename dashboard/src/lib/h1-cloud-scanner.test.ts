import test from "node:test";
import assert from "node:assert/strict";
import {
  H1_ALL_BASES,
  H1_CLOUD_STATE_VERSION,
  H1_FIRST_SCAN_HOUR,
  H1_HISTORY_RETENTION_CALENDAR_DAYS,
  H1_SIGNAL_RULE_VERSION,
  H1_TARGET_BASES,
  H1_POST_SIGNAL_ACTIVE_WEEKDAYS,
  H1_SCAN_END_HOUR,
  H1_SCAN_HOURS,
  H1_SCAN_START_HOUR,
  audusdH3SignalForXauH4,
  backfillSuppressedHistory,
  baseSymbolForTarget,
  baseSymbolForTargetSlot,
  buildPublicFeed,
  buildStoredAlert,
  buildTelegramMessage,
  configuredPostSignalDecision,
  emptyCloudState,
  findH1PatternMatches,
  findH1PatternMatchesForTarget,
  postSignalDecision,
  reconcileTradeState,
  scannerBaseForTarget,
  seedCloudStateFromPublic,
  signalFromBaseAfterCalendar,
  signalFromPatternBase,
  signalFromTargetBase,
  trimCloudState,
  type H1Direction,
  type H1DirectionBar,
} from "./h1-cloud-scanner.ts";

function bars(sequenceOldestToNewest: string, startHour = 1, date = "2026-08-21"): H1DirectionBar[] {
  return [...sequenceOldestToNewest].map((direction, index) => {
    const hour = startHour + index;
    return {
      hour,
      brokerDate: date,
      brokerTime: `${date}T${String(hour).padStart(2, "0")}:00`,
      direction: direction as H1Direction,
    };
  });
}

test("history retention keeps the inclusive 90-calendar-day boundary and removes the prior day", () => {
  assert.equal(H1_HISTORY_RETENTION_CALENDAR_DAYS, 90);
  const state = emptyCloudState();
  for (const date of ["2026-05-25", "2026-05-26", "2026-08-21", "2026-08-23"]) state.days[date] = { symbols: {} };
  trimCloudState(state);
  assert.deepEqual(Object.keys(state.days).sort(), ["2026-05-26", "2026-08-21", "2026-08-23"]);
});

test("history retention counts calendar days rather than stored trading-day keys", () => {
  const state = emptyCloudState();
  for (const date of ["2026-05-25", "2026-05-26", "2026-06-01", "2026-07-15", "2026-08-23"]) state.days[date] = { symbols: {} };
  trimCloudState(state);
  assert.deepEqual(Object.keys(state.days).sort(), ["2026-05-26", "2026-06-01", "2026-07-15", "2026-08-23"]);
});

test("scanner exposes H3 H4 and H06-H16 active slots while H5 is excluded", () => {
  assert.equal(H1_FIRST_SCAN_HOUR, 3);
  assert.equal(H1_SCAN_START_HOUR, 6);
  assert.equal(H1_SCAN_END_HOUR, 16);
  assert.deepEqual(H1_SCAN_HOURS, [3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]);

  const pureTgg = findH1PatternMatches(bars("GGT", 3), 18).filter((item) => item.slotHour === 6);
  const pureGtt = findH1PatternMatches(bars("TTG", 3), 18).filter((item) => item.slotHour === 6);
  const tripleT = findH1PatternMatches(bars("TTT", 3), 18).filter((item) => item.slotHour === 6);
  const tripleG = findH1PatternMatches(bars("GGG", 3), 18).filter((item) => item.slotHour === 6);
  const normalT = findH1PatternMatches(bars("TTTT", 2), 18).filter((item) => item.slotHour === 6);
  const normalG = findH1PatternMatches(bars("GGGG", 2), 18).filter((item) => item.slotHour === 6);
  assert.deepEqual(pureTgg.map((item) => [item.pattern.join(""), item.patternKind]), [["TGG", "sw3Pure"]]);
  assert.deepEqual(pureGtt.map((item) => [item.pattern.join(""), item.patternKind]), [["GTT", "sw3Pure"]]);
  assert.deepEqual(tripleT, []);
  assert.deepEqual(tripleG, []);
  assert.deepEqual(normalT.map((item) => [item.pattern.join(""), item.patternKind]), [["TTTT", "sw3Normal"]]);
  assert.deepEqual(normalG.map((item) => [item.pattern.join(""), item.patternKind]), [["GGGG", "sw3Normal"]]);

  assert.equal(findH1PatternMatches(bars("GGT", 2), 18).some((item) => item.slotHour === 5), false);
  assert.equal(findH1PatternMatches(bars("GGT", 13), 18).some((item) => item.slotHour === 16), true);
  assert.equal(findH1PatternMatches(bars("GGT", 14), 18).some((item) => item.slotHour === 17), false);
  assert.equal(findH1PatternMatches(bars("GT", 1), 18).some((item) => item.patternKind === "sw2"), false);
});

test("two-candle patterns are exclusive to H3 FX and H4 XAUUSD", () => {
  for (const sequence of ["GT", "TG", "TT", "GG"]) {
    const fx = findH1PatternMatchesForTarget("GBPUSD", bars(sequence, 1), 3);
    assert.deepEqual(fx.map((item) => [item.slotHour, item.pattern.join(""), item.patternKind]), [[3, [...sequence].reverse().join(""), "sw2"]]);

    const xauBeforeH4 = findH1PatternMatchesForTarget("XAUUSD", bars(sequence, 2), 3);
    assert.equal(xauBeforeH4.some((item) => item.patternKind === "sw2"), false);

    const xau = findH1PatternMatchesForTarget("XAUUSD", bars(sequence, 2), 4);
    assert.deepEqual(xau.map((item) => [item.slotHour, item.pattern.join(""), item.patternKind]), [[4, [...sequence].reverse().join(""), "sw2"]]);
  }

  for (const base of ["GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const) {
    const cumulativeAtH4 = findH1PatternMatchesForTarget(base, bars("GT", 1), 4);
    assert.deepEqual(cumulativeAtH4.map((item) => [item.slotHour, item.pattern.join(""), item.patternKind]), [[3, "TG", "sw2"]]);
    assert.equal(cumulativeAtH4.some((item) => item.slotHour === 4), false);
  }
});

test("target base polarity applies before Thursday Friday post-signal", () => {
  const fxMatch = findH1PatternMatchesForTarget("GBPUSD", bars("GT", 1, "2026-07-02"), 3).find((item) => item.slotHour === 3)!;
  const fx = buildStoredAlert({
    base: "GBPUSD",
    brokerSymbol: "GBPUSD",
    scannerBase: "GBPUSD",
    scannerSymbol: "GBPUSD",
    match: fxMatch,
    baseSymbol: "EURUSD",
    baseBar: bars("T", 2, "2026-07-02")[0],
  });
  assert.deepEqual([fx.patternKind, fx.baseSymbol, fx.baseH1Signal, fx.postSignalRule, fx.symbolH1Signal], ["sw2", "EURUSD", "BUY", "thu-cycle", "BUY"]);
  assert.equal(fx.lookbackAction, "none");

  const xauMatch = findH1PatternMatchesForTarget("XAUUSD", bars("GT", 2, "2026-08-21"), 4).find((item) => item.slotHour === 4)!;
  const xau = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    scannerBase: "XAUUSD",
    scannerSymbol: "XAUUSD",
    match: xauMatch,
    baseSymbol: "GBPUSD",
    baseBar: bars("G", 3, "2026-08-21")[0],
  });
  assert.deepEqual([xau.patternKind, xau.baseSymbol, xau.baseH1Signal, xau.postSignalRule, xau.symbolH1Signal], ["sw2", "GBPUSD", "SELL", "fri-cycle", "BUY"]);
  assert.equal(xau.lookbackAction, "none");

  const monday = buildStoredAlert({
    base: "GBPUSD",
    brokerSymbol: "GBPUSD",
    scannerBase: "GBPUSD",
    scannerSymbol: "GBPUSD",
    match: findH1PatternMatchesForTarget("GBPUSD", bars("GT", 1, "2026-08-17"), 3).find((item) => item.slotHour === 3)!,
    baseSymbol: "EURUSD",
    baseBar: bars("T", 2, "2026-08-17")[0],
  });
  assert.deepEqual([monday.baseSymbol, monday.postSignalRule, monday.baseH1Signal, monday.symbolH1Signal], ["EURUSD", "none", "BUY", "SELL"]);

  const usdJpy = buildStoredAlert({
    base: "USDJPY",
    brokerSymbol: "USDJPY",
    scannerBase: "USDJPY",
    scannerSymbol: "USDJPY",
    match: findH1PatternMatchesForTarget("USDJPY", bars("GT", 1, "2026-08-17"), 3).find((item) => item.slotHour === 3)!,
    baseSymbol: "USDCAD",
    baseBar: bars("T", 2, "2026-08-17")[0],
  });
  assert.deepEqual([usdJpy.baseSymbol, usdJpy.postSignalRule, usdJpy.baseH1Signal, usdJpy.symbolH1Signal], ["USDCAD", "none", "BUY", "SELL"]);
  assert.match(buildTelegramMessage("USDJPY", "2026-08-17", usdJpy), /Logic base: đảo ngược USDCAD H1/);
});

test("FX H6 checks H2 H1 pair before H3 H2 H1 triple", () => {
  const cases = [
    ["TGG", "TGG", "block-pattern1", false],
    ["GTT", "GTT", "block-pattern1", false],
    ["TTT", "TTTT", "block-pattern2", false],
    ["GGG", "GGGG", "block-pattern2", false],
    ["TGT", "GT", "block-pair", false],
    ["GTG", "TG", "block-pair", false],
    ["TTG", "TG", "block-pair", false],
    ["GGT", "GT", "block-pair", false],
  ] as const;

  for (const [lookback, expectedPattern, action, tradeAllowed] of cases) {
    const [h3, h2, h1] = [...lookback] as H1Direction[];
    const h4: H1Direction = h3 === "G" ? "G" : "T";
    const h5: H1Direction = h3 === "G" ? "T" : "G";
    const fxH6Bars: H1DirectionBar[] = [
      { hour: 1, brokerDate: "2026-08-21", brokerTime: "2026-08-21T01:00", direction: h1 },
      { hour: 2, brokerDate: "2026-08-21", brokerTime: "2026-08-21T02:00", direction: h2 },
      { hour: 3, brokerDate: "2026-08-21", brokerTime: "2026-08-21T03:00", direction: h3 },
      { hour: 4, brokerDate: "2026-08-21", brokerTime: "2026-08-21T04:00", direction: h4 },
      { hour: 5, brokerDate: "2026-08-21", brokerTime: "2026-08-21T05:00", direction: h5 },
    ];

    for (const base of ["GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const) {
      const fxH6 = findH1PatternMatchesForTarget(base, fxH6Bars, 6).find((item) => item.slotHour === 6)!;
      assert.deepEqual([fxH6.lookbackPattern, fxH6.lookbackAction, fxH6.tradeAllowed], [expectedPattern, action, tradeAllowed]);
    }
  }

  const invertedMatch = findH1PatternMatchesForTarget("GBPUSD", [
    { hour: 1, brokerDate: "2026-08-17", brokerTime: "2026-08-17T01:00", direction: "T" },
    { hour: 2, brokerDate: "2026-08-17", brokerTime: "2026-08-17T02:00", direction: "G" },
    { hour: 3, brokerDate: "2026-08-17", brokerTime: "2026-08-17T03:00", direction: "T" },
    { hour: 4, brokerDate: "2026-08-17", brokerTime: "2026-08-17T04:00", direction: "T" },
    { hour: 5, brokerDate: "2026-08-17", brokerTime: "2026-08-17T05:00", direction: "G" },
  ], 6).find((item) => item.slotHour === 6)!;
  const alert = buildStoredAlert({
    base: "GBPUSD",
    brokerSymbol: "GBPUSD",
    scannerBase: "GBPUSD",
    scannerSymbol: "GBPUSD",
    match: invertedMatch,
    baseSymbol: "EURUSD",
    baseBar: bars("T", 5, "2026-08-17")[0],
  });
  assert.deepEqual([alert.lookbackPattern, alert.lookbackAction, alert.baseH1Signal, alert.symbolH1Signal], ["GT", "block-pair", "BUY", "SELL"]);
});

test("FX H7 uses H3 H2 H1 primary and H4 H3 H2 fallback like H8", () => {
  for (const base of ["GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const) {
    const primary = findH1PatternMatchesForTarget(base, bars("TGTGGT", 1), 7).find((item) => item.slotHour === 7)!;
    assert.deepEqual(
      [primary.pattern.join(""), primary.lookbackPattern, primary.lookbackAction, primary.tradeAllowed],
      ["TGG", "TGT", "invert-pattern3", true],
    );

    const fallback = findH1PatternMatchesForTarget(base, bars("GTTGGT", 1), 7).find((item) => item.slotHour === 7)!;
    assert.deepEqual(
      [fallback.pattern.join(""), fallback.lookbackPattern, fallback.lookbackAction, fallback.tradeAllowed],
      ["TGG", "GTT", "block-pattern1", false],
    );

    const pattern2 = findH1PatternMatchesForTarget(base, bars("GGTTTT", 1), 7).find((item) => item.slotHour === 7)!;
    assert.deepEqual(
      [pattern2.pattern.join(""), pattern2.patternKind, pattern2.lookbackPattern, pattern2.lookbackAction, pattern2.tradeAllowed],
      ["TTTT", "sw3Normal", "TGG", "block-pattern1", false],
    );
  }
});

test("XAUUSD H6 keeps the H3 H2 pair gate", () => {
  for (const [pair, blocked] of [["TG", true], ["GT", true], ["TT", false], ["GG", false]] as const) {
    const [newer, older] = [...pair];
    const h5Lead: H1Direction = newer === "T" ? "G" : "T";
    const xauH6Bars = [
      { hour: 2, brokerDate: "2026-08-21", brokerTime: "2026-08-21T02:00", direction: older as H1Direction },
      { hour: 3, brokerDate: "2026-08-21", brokerTime: "2026-08-21T03:00", direction: newer as H1Direction },
      { hour: 4, brokerDate: "2026-08-21", brokerTime: "2026-08-21T04:00", direction: newer as H1Direction },
      { hour: 5, brokerDate: "2026-08-21", brokerTime: "2026-08-21T05:00", direction: h5Lead },
    ];
    const xauH6 = findH1PatternMatchesForTarget("XAUUSD", xauH6Bars, 6).find((item) => item.slotHour === 6)!;
    assert.deepEqual([xauH6.patternKind, xauH6.lookbackPattern, xauH6.lookbackAction, xauH6.tradeAllowed], ["sw3Pure", pair, blocked ? "block-pair" : "none", !blocked]);
  }

  const xauH6Pattern2 = findH1PatternMatchesForTarget("XAUUSD", bars("GTTTT", 1), 6).find((item) => item.slotHour === 6)!;
  assert.deepEqual([xauH6Pattern2.pattern.join(""), xauH6Pattern2.patternKind, xauH6Pattern2.lookbackPattern, xauH6Pattern2.lookbackAction, xauH6Pattern2.tradeAllowed], ["TTTT", "sw3Normal", "TT", "none", true]);
});

test("XAUUSD H7 checks H3 H2 pair before H4 H3 H2 triple", () => {
  const cases = [
    ["TGG", "TGG", "block-pattern1", false],
    ["GTT", "GTT", "block-pattern1", false],
    ["TTT", "TTTT", "block-pattern2", false],
    ["GGG", "GGGG", "block-pattern2", false],
    ["TGT", "GT", "block-pair", false],
    ["GTG", "TG", "block-pair", false],
    ["TTG", "TG", "block-pair", false],
    ["GGT", "GT", "block-pair", false],
  ] as const;

  for (const [lookback, expectedPattern, action, tradeAllowed] of cases) {
    const [h4, h3, h2] = [...lookback] as H1Direction[];
    const h5: H1Direction = h4;
    const h6: H1Direction = h4 === "T" ? "G" : "T";
    const xauH7Bars: H1DirectionBar[] = [
      { hour: 2, brokerDate: "2026-08-21", brokerTime: "2026-08-21T02:00", direction: h2 },
      { hour: 3, brokerDate: "2026-08-21", brokerTime: "2026-08-21T03:00", direction: h3 },
      { hour: 4, brokerDate: "2026-08-21", brokerTime: "2026-08-21T04:00", direction: h4 },
      { hour: 5, brokerDate: "2026-08-21", brokerTime: "2026-08-21T05:00", direction: h5 },
      { hour: 6, brokerDate: "2026-08-21", brokerTime: "2026-08-21T06:00", direction: h6 },
    ];
    const xauH7 = findH1PatternMatchesForTarget("XAUUSD", xauH7Bars, 7).find((item) => item.slotHour === 7)!;
    assert.deepEqual([xauH7.lookbackPattern, xauH7.lookbackAction, xauH7.tradeAllowed], [expectedPattern, action, tradeAllowed]);
  }

  const invertedMatch = findH1PatternMatchesForTarget("XAUUSD", [
    { hour: 2, brokerDate: "2026-08-17", brokerTime: "2026-08-17T02:00", direction: "T" },
    { hour: 3, brokerDate: "2026-08-17", brokerTime: "2026-08-17T03:00", direction: "G" },
    { hour: 4, brokerDate: "2026-08-17", brokerTime: "2026-08-17T04:00", direction: "T" },
    { hour: 5, brokerDate: "2026-08-17", brokerTime: "2026-08-17T05:00", direction: "T" },
    { hour: 6, brokerDate: "2026-08-17", brokerTime: "2026-08-17T06:00", direction: "G" },
  ], 7).find((item) => item.slotHour === 7)!;
  const alert = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    scannerBase: "XAUUSD",
    scannerSymbol: "XAUUSD",
    match: invertedMatch,
    baseSymbol: "GBPUSD",
    baseBar: bars("T", 6, "2026-08-17")[0],
  });
  assert.deepEqual([alert.lookbackPattern, alert.lookbackAction, alert.baseH1Signal, alert.symbolH1Signal], ["GT", "block-pair", "BUY", "BUY"]);

  for (const base of ["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const) {
    assert.equal(findH1PatternMatchesForTarget(base, bars("GTTT", 1), 5).some((item) => item.slotHour === 5), false);
  }
  const fxH7 = findH1PatternMatchesForTarget("GBPUSD", bars("GTGGT", 2), 7).find((item) => item.slotHour === 7)!;
  assert.deepEqual([fxH7.lookbackPattern, fxH7.lookbackAction, fxH7.tradeAllowed], [null, "none", true]);
});

test("Pattern 2 requires four same-direction candles and emits a long run only once", () => {
  for (const direction of ["T", "G"] as const) {
    const triple = findH1PatternMatches(bars(direction.repeat(3), 3), 6).filter((item) => item.slotHour === 6);
    assert.deepEqual(triple, []);

    const run4 = findH1PatternMatches(bars(direction.repeat(4), 2), 6).filter((item) => item.slotHour === 6);
    const run5AtOpen = findH1PatternMatches(bars(direction.repeat(5), 1), 6).filter((item) => item.slotHour === 6);
    assert.deepEqual(run4.map((item) => [item.pattern.join(""), item.patternKind]), [[direction.repeat(4), "sw3Normal"]]);
    assert.deepEqual(run5AtOpen.map((item) => [item.pattern.join(""), item.patternKind]), [[direction.repeat(4), "sw3Normal"]]);

    const run5AcrossSlots = findH1PatternMatches(bars(`G${direction.repeat(5)}`, 1), 7).filter((item) => item.patternKind === "sw3Normal");
    assert.equal(run5AcrossSlots.length, 1);
  }
});

test("only the first daily Pattern 2 is scanned while later Pattern 2 matches are omitted", () => {
  const matches = findH1PatternMatchesForTarget("GBPUSD", bars("GTTTTGGGG", 1), 10);
  const first = matches.find((item) => item.slotHour === 6)!;
  const later = matches.find((item) => item.slotHour === 10);

  assert.deepEqual([first.pattern.join(""), first.patternKind, first.lookbackPattern, first.lookbackAction, first.tradeAllowed], ["TTTT", "sw3Normal", "TG", "block-pair", false]);
  assert.equal(later, undefined);
  assert.equal(matches.filter((item) => item.patternKind === "sw3Normal").length, 1);

  const pattern1AfterPattern2 = findH1PatternMatchesForTarget("GBPUSD", bars("GTTTTG", 1), 7).find((item) => item.slotHour === 7)!;
  assert.deepEqual([pattern1AfterPattern2.pattern.join(""), pattern1AfterPattern2.patternKind, pattern1AfterPattern2.lookbackAction, pattern1AfterPattern2.tradeAllowed], ["GTT", "sw3Pure", "block-pattern2", false]);
});

test("GBPUSD AUDUSD USDCAD and USDJPY invert configured base while XAUUSD keeps base before later layers", () => {
  for (const base of ["GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const) {
    assert.equal(signalFromTargetBase(base, "BUY"), "SELL");
    assert.equal(signalFromTargetBase(base, "SELL"), "BUY");
  }
  for (const base of ["XAUUSD"] as const) {
    assert.equal(signalFromTargetBase(base, "BUY"), "BUY");
    assert.equal(signalFromTargetBase(base, "SELL"), "SELL");
  }
  for (const kind of ["sw2", "sw3Pure", "sw3Normal"] as const) {
    assert.equal(signalFromPatternBase("BUY", kind), "BUY");
    assert.equal(signalFromPatternBase("SELL", kind), "SELL");
  }
  for (const slot of [5, 6, 7, 8, 15, 16, 17]) {
    assert.equal(signalFromBaseAfterCalendar("BUY", "2026-08-17", slot), "BUY");
    assert.equal(signalFromBaseAfterCalendar("SELL", "2026-08-17", slot), "SELL");
  }
});

test("target scanner/base mapping follows the five-symbol signal loop", () => {
  assert.equal(H1_CLOUD_STATE_VERSION, 35);
  assert.equal(H1_SIGNAL_RULE_VERSION, 29);
  assert.deepEqual(H1_TARGET_BASES, ["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY"]);
  assert.deepEqual(H1_ALL_BASES, ["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY", "EURUSD"]);

  assert.equal(scannerBaseForTarget("XAUUSD"), "XAUUSD");
  assert.equal(baseSymbolForTarget("XAUUSD"), "GBPUSD");
  assert.equal(baseSymbolForTargetSlot("XAUUSD", 4), "AUDUSD");
  assert.equal(baseSymbolForTargetSlot("XAUUSD", 6), "GBPUSD");

  assert.equal(scannerBaseForTarget("GBPUSD"), "GBPUSD");
  assert.equal(baseSymbolForTarget("GBPUSD"), "EURUSD");

  assert.equal(scannerBaseForTarget("AUDUSD"), "AUDUSD");
  assert.equal(baseSymbolForTarget("AUDUSD"), "XAUUSD");

  assert.equal(scannerBaseForTarget("USDCAD"), "USDCAD");
  assert.equal(baseSymbolForTarget("USDCAD"), "GBPUSD");

  assert.equal(scannerBaseForTarget("USDJPY"), "USDJPY");
  assert.equal(baseSymbolForTarget("USDJPY"), "USDCAD");
});

test("USDCAD scans itself and inverts GBPUSD base", () => {
  const match = findH1PatternMatchesForTarget("USDCAD", bars("GT", 1, "2026-08-17"), 3).find((item) => item.slotHour === 3)!;
  const alert = buildStoredAlert({
    base: "USDCAD",
    brokerSymbol: "USDCAD",
    scannerBase: "USDCAD",
    scannerSymbol: "USDCAD",
    match,
    baseSymbol: "GBPUSD",
    baseBar: bars("T", 2, "2026-08-17")[0],
  });
  assert.deepEqual([alert.scannerBase, alert.baseSymbol, alert.baseH1Signal, alert.symbolH1Signal], ["USDCAD", "GBPUSD", "BUY", "SELL"]);
  assert.match(buildTelegramMessage("USDCAD", "2026-08-17", alert), /Logic base: đảo ngược GBPUSD H1/);
});

test("active post-signal keeps Monday Tuesday Wednesday off and enables Thursday Friday cycles", () => {
  assert.deepEqual(H1_POST_SIGNAL_ACTIVE_WEEKDAYS, [4, 5]);
  for (const [date, slot] of [["2026-08-17", 3], ["2026-08-18", 4], ["2026-08-19", 12]] as const) {
    assert.deepEqual(postSignalDecision(date, slot), { inverted: false, rule: "none" });
    assert.equal(signalFromBaseAfterCalendar("BUY", date, slot), "BUY");
    assert.equal(signalFromBaseAfterCalendar("SELL", date, slot), "SELL");
  }
  assert.deepEqual(postSignalDecision("2026-07-02", 8), { inverted: true, rule: "thu-cycle" });
  assert.deepEqual(postSignalDecision("2026-08-21", 14), { inverted: true, rule: "fri-cycle" });
  assert.equal(signalFromBaseAfterCalendar("BUY", "2026-07-02", 8), "SELL");
  assert.equal(signalFromBaseAfterCalendar("SELL", "2026-08-21", 14), "BUY");
  assert.deepEqual(postSignalDecision("2026-08-06", 8), { inverted: false, rule: "none" });
  assert.deepEqual(postSignalDecision("2026-05-01", 8), { inverted: false, rule: "none" });
});

test("configured Monday Tuesday Wednesday post-signal rules remain intact behind the test bypass", () => {
  for (const slot of [3, 4, 9, 10, 11, 12, 13, 14]) assert.equal(configuredPostSignalDecision("2026-08-17", slot).inverted, true);
  for (const slot of [5, 6, 7, 8, 15, 16, 17]) assert.equal(configuredPostSignalDecision("2026-08-17", slot).inverted, false);
  for (const slot of [3, 4, 9, 10, 11]) assert.equal(configuredPostSignalDecision("2026-08-18", slot).inverted, true);
  for (const slot of [5, 8, 12, 13, 14, 17]) assert.equal(configuredPostSignalDecision("2026-08-18", slot).inverted, false);
  for (const slot of [3, 4, 12, 13, 14]) assert.equal(configuredPostSignalDecision("2026-08-19", slot).inverted, true);
  for (const slot of [5, 8, 9, 10, 11, 15, 17]) assert.equal(configuredPostSignalDecision("2026-08-19", slot).inverted, false);
});

test("configured Thursday special cycle remains intact behind the test bypass", () => {
  assert.deepEqual(configuredPostSignalDecision("2026-07-02", 8), { inverted: true, rule: "thu-cycle" });
  assert.deepEqual(configuredPostSignalDecision("2026-07-30", 14), { inverted: true, rule: "thu-cycle" });
  assert.deepEqual(configuredPostSignalDecision("2026-08-06", 8), { inverted: false, rule: "none" });
  assert.deepEqual(configuredPostSignalDecision("2026-08-13", 14), { inverted: false, rule: "none" });
  assert.deepEqual(configuredPostSignalDecision("2026-10-01", 8), { inverted: true, rule: "thu-cycle" });
  assert.deepEqual(configuredPostSignalDecision("2026-10-08", 14), { inverted: true, rule: "thu-cycle" });
});

test("configured Friday special cycle remains intact behind the test bypass", () => {
  assert.deepEqual(configuredPostSignalDecision("2026-05-01", 8), { inverted: false, rule: "none" });
  assert.deepEqual(configuredPostSignalDecision("2026-05-08", 14), { inverted: false, rule: "none" });
  assert.deepEqual(configuredPostSignalDecision("2026-08-07", 8), { inverted: true, rule: "fri-cycle" });
  assert.deepEqual(configuredPostSignalDecision("2026-08-21", 14), { inverted: true, rule: "fri-cycle" });
  assert.deepEqual(configuredPostSignalDecision("2026-09-04", 8), { inverted: true, rule: "fri-cycle" });
});

test("lookback distinguishes exact Pattern 4 triples from Pattern 2 runs of four or more", () => {
  const exactPattern4 = findH1PatternMatches(bars("GTTTGGT", 1), 8).find((item) => item.slotHour === 8)!;
  assert.deepEqual(
    [exactPattern4.pattern.join(""), exactPattern4.lookbackPattern, exactPattern4.lookbackAction, exactPattern4.tradeAllowed],
    ["TGG", "TTT", "block-pattern4", false],
  );

  const primaryPattern2 = findH1PatternMatches(bars("GTTTTTG", 1), 8).find((item) => item.slotHour === 8)!;
  assert.deepEqual(
    [primaryPattern2.pattern.join(""), primaryPattern2.lookbackPattern, primaryPattern2.lookbackAction, primaryPattern2.tradeAllowed],
    ["GTT", "TTTTT", "block-pattern2", false],
  );

  const fallbackPattern2 = findH1PatternMatches(bars("GGTTTTG", 1), 8).find((item) => item.slotHour === 8)!;
  assert.deepEqual(
    [fallbackPattern2.pattern.join(""), fallbackPattern2.lookbackPattern, fallbackPattern2.lookbackAction, fallbackPattern2.tradeAllowed],
    ["GTT", "TTTT", "block-pattern2", false],
  );
});

test("FX H7+ and XAU H8+ evaluate only the lùi-3 three-candle window first", () => {
  const blockedByPattern1 = findH1PatternMatches(bars("GGTGGT", 2), 8).find((item) => item.slotHour === 8)!;
  assert.deepEqual([blockedByPattern1.pattern.join(""), blockedByPattern1.lookbackPattern, blockedByPattern1.lookbackAction, blockedByPattern1.tradeAllowed], ["TGG", "TGG", "block-pattern1", false]);

  const primaryPattern4T = findH1PatternMatches(bars("TTTGGT", 2), 8).find((item) => item.slotHour === 8)!;
  assert.deepEqual([primaryPattern4T.lookbackPattern, primaryPattern4T.lookbackAction, primaryPattern4T.tradeAllowed], ["TTT", "block-pattern4", false]);

  const primaryPattern4G = findH1PatternMatches(bars("GGGTTG", 2), 8).find((item) => item.slotHour === 8)!;
  assert.deepEqual([primaryPattern4G.lookbackPattern, primaryPattern4G.lookbackAction, primaryPattern4G.tradeAllowed], ["GGG", "block-pattern4", false]);

  const invertedByPattern3 = findH1PatternMatches(bars("TGTGGT", 2), 8).find((item) => item.slotHour === 8)!;
  assert.deepEqual([invertedByPattern3.lookbackPattern, invertedByPattern3.lookbackAction, invertedByPattern3.tradeAllowed], ["TGT", "invert-pattern3", true]);

  const atH7 = findH1PatternMatches(bars("TTTGGT", 1), 7).find((item) => item.slotHour === 7)!;
  assert.deepEqual([atH7.lookbackPattern, atH7.lookbackAction, atH7.tradeAllowed], ["TTT", "block-pattern4", false]);
});

test("FX H7+ and XAU H8+ evaluate the lùi-2 three-candle window only when lùi 3 has no action", () => {
  const fallbackPattern1 = findH1PatternMatches(bars("GTTGGT", 2), 8).find((item) => item.slotHour === 8)!;
  assert.deepEqual([fallbackPattern1.pattern.join(""), fallbackPattern1.lookbackPattern, fallbackPattern1.lookbackAction, fallbackPattern1.tradeAllowed], ["TGG", "GTT", "block-pattern1", false]);

  const fallbackPattern2T = findH1PatternMatches(bars("GTTTTG", 2), 8).find((item) => item.slotHour === 8)!;
  assert.deepEqual([fallbackPattern2T.pattern.join(""), fallbackPattern2T.lookbackPattern, fallbackPattern2T.lookbackAction, fallbackPattern2T.tradeAllowed], ["GTT", "TTTT", "block-pattern2", false]);

  const fallbackPattern2G = findH1PatternMatches(bars("TGGGGT", 2), 8).find((item) => item.slotHour === 8)!;
  assert.deepEqual([fallbackPattern2G.pattern.join(""), fallbackPattern2G.lookbackPattern, fallbackPattern2G.lookbackAction, fallbackPattern2G.tradeAllowed], ["TGG", "GGGG", "block-pattern2", false]);
});

test("Pattern 2 has normal priority and obeys three-candle lookback gates", () => {
  const blocked = findH1PatternMatches(bars("GGTTTT", 2), 8).find((item) => item.slotHour === 8)!;
  assert.deepEqual([blocked.pattern.join(""), blocked.patternKind, blocked.lookbackPattern, blocked.lookbackAction, blocked.tradeAllowed], ["TTTT", "sw3Normal", "TGG", "block-pattern1", false]);

  const inverted = findH1PatternMatches(bars("TGTTTT", 2), 8).find((item) => item.slotHour === 8)!;
  assert.deepEqual([inverted.pattern.join(""), inverted.patternKind, inverted.lookbackPattern, inverted.lookbackAction, inverted.tradeAllowed], ["TTTT", "sw3Normal", "TGT", "invert-pattern3", true]);
});

test("first daily Pattern 2 obeys target pair and triple lookback gates", () => {
  for (const base of ["GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const) {
    const fxH6 = findH1PatternMatchesForTarget(base, bars("GTTTT", 1), 6).find((item) => item.slotHour === 6)!;
    assert.deepEqual(
      [fxH6.pattern.join(""), fxH6.patternKind, fxH6.lookbackPattern, fxH6.lookbackAction, fxH6.tradeAllowed],
      ["TTTT", "sw3Normal", "TG", "block-pair", false],
    );
  }

  const xauH7 = findH1PatternMatchesForTarget("XAUUSD", bars("GTTTT", 2), 7).find((item) => item.slotHour === 7)!;
  assert.deepEqual(
    [xauH7.pattern.join(""), xauH7.patternKind, xauH7.lookbackPattern, xauH7.lookbackAction, xauH7.tradeAllowed],
    ["TTTT", "sw3Normal", "TG", "block-pair", false],
  );
});

test("Pattern 3 lookback inversion is independent from post-signal inversion", () => {
  const match = findH1PatternMatches(bars("TGTGGT", 2, "2026-08-21"), 8).find((item) => item.slotHour === 8)!;
  const alert = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    scannerBase: "XAUUSD",
    scannerSymbol: "XAUUSD",
    match,
    baseSymbol: "GBPUSD",
    baseBar: bars("T", 7, "2026-08-21")[0],
  });
  assert.equal(alert.baseH1Signal, "BUY");
  assert.equal(alert.lookbackAction, "invert-pattern3");
  assert.equal(alert.postSignalRule, "fri-cycle");
  assert.equal(alert.symbolH1Signal, "BUY");
});

test("stored rows reconcile blockedSlots from allowTrade state", () => {
  const blockedMatch = findH1PatternMatches(bars("GGTGGT", 2), 8).find((item) => item.slotHour === 8)!;
  const allowedMatch = findH1PatternMatches(bars("GGT", 3), 6).find((item) => item.slotHour === 6)!;
  const alerts = [blockedMatch, allowedMatch].map((match, index) => buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    scannerBase: "XAUUSD",
    scannerSymbol: "XAUUSD",
    match: { ...match, slotHour: 8 + index },
    baseSymbol: "GBPUSD",
    baseBar: bars("T", 7 + index)[0],
  }));
  const symbolState = { alerts, blockedSlots: [6, 7] };
  assert.equal(reconcileTradeState(symbolState), true);
  assert.deepEqual(symbolState.blockedSlots, [8]);
  assert.equal(reconcileTradeState(symbolState), false);
});

test("accepted pure SW3 Telegram marks /!\\ with no repeat warning metadata", () => {
  const match = findH1PatternMatches(bars("GGT", 3), 6).find((item) => item.slotHour === 6)!;
  const alert = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    scannerBase: "XAUUSD",
    scannerSymbol: "XAUUSD",
    match,
    baseSymbol: "GBPUSD",
    baseBar: bars("T", 5)[0],
  });
  assert.equal(alert.patternKind, "sw3Pure");
  assert.equal(alert.baseH1Signal, "BUY");
  assert.equal(alert.symbolH1Signal, "SELL");
  assert.equal(alert.postSignalRule, "fri-cycle");
  const message = buildTelegramMessage("XAUUSD", "2026-08-21", alert);
  assert.match(message, /\/!\\ SW 3 cây thuần/);
  assert.match(message, /Logic base: giữ nguyên GBPUSD H1/);
  assert.match(message, /Hậu signal: đảo theo chu kỳ Thứ 6 special/);
  assert.match(message, /Signal XAUUSD H1: SELL/);
  assert.doesNotMatch(message, /đã xuất hiện|vẫn tính signal|Hậu kiểm|post-check/i);
});

test("Pattern 2 applies target base polarity before active Friday post-signal inversion", () => {
  const match = findH1PatternMatches(bars("TTTT", 2), 6).find((item) => item.slotHour === 6)!;
  const alert = buildStoredAlert({
    base: "GBPUSD",
    brokerSymbol: "GBPUSD",
    scannerBase: "GBPUSD",
    scannerSymbol: "GBPUSD",
    match,
    baseSymbol: "EURUSD",
    baseBar: bars("G", 5)[0],
  });
  assert.equal(alert.patternKind, "sw3Normal");
  assert.equal(alert.baseH1Signal, "SELL");
  assert.equal(alert.postSignalRule, "fri-cycle");
  assert.equal(alert.symbolH1Signal, "SELL");
  assert.match(buildTelegramMessage("GBPUSD", "2026-08-21", alert), /Logic base: đảo ngược EURUSD H1/);
  assert.equal("previousPureSlot" in alert, false);
});

test("fresh H4 state backfills FX H3 while keeping H4 exclusive to XAUUSD", () => {
  const state = emptyCloudState();
  state.days["2026-08-25"] = {
    suppressedThroughHour: 4,
    symbols: Object.fromEntries(["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY"].map((base) => [base, { alerts: [], blockedSlots: [] }])),
  };
  const market = {
    GBPUSD: { displayName: "GBPUSD", bars: bars("GTG", 1, "2026-08-25") },
    XAUUSD: { displayName: "XAUUSD", bars: bars("TGT", 1, "2026-08-25") },
    AUDUSD: { displayName: "AUDUSD", bars: bars("GGT", 1, "2026-08-25") },
    USDCAD: { displayName: "USDCAD", bars: bars("TGG", 1, "2026-08-25") },
    USDJPY: { displayName: "USDJPY", bars: bars("GTG", 1, "2026-08-25") },
    EURUSD: { displayName: "EURUSD", bars: bars("TGG", 1, "2026-08-25") },
  } as const;

  assert.equal(backfillSuppressedHistory(state, "2026-08-25", market), 5);
  for (const base of ["GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const) {
    assert.ok(state.days["2026-08-25"].symbols[base]?.alerts.some((alert) => alert.slotHour === 3));
    assert.equal(state.days["2026-08-25"].symbols[base]?.alerts.some((alert) => alert.slotHour === 4), false);
  }
  const xauH4 = state.days["2026-08-25"].symbols.XAUUSD?.alerts.find((alert) => alert.slotHour === 4);
  assert.ok(xauH4);
  const audusdH3Signal = audusdH3SignalForXauH4(market.AUDUSD.bars, market.XAUUSD.bars);
  assert.deepEqual([xauH4.baseSymbol, xauH4.baseHour, xauH4.baseH1Signal, xauH4.symbolH1Signal], ["AUDUSD", 3, audusdH3Signal, audusdH3Signal]);
  assert.match(buildTelegramMessage("XAUUSD", "2026-08-25", xauH4), /Logic base: lấy signal AUDUSD H3/);
});

test("fresh H5 recovery restores prior H3 H4 slots without creating an H5 signal", () => {
  const state = emptyCloudState();
  state.days["2026-08-25"] = {
    suppressedThroughHour: 5,
    symbols: Object.fromEntries(["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY"].map((base) => [base, { alerts: [], blockedSlots: [] }])),
  };
  const market = {
    GBPUSD: { displayName: "GBPUSD", bars: bars("GTGG", 1, "2026-08-25") },
    XAUUSD: { displayName: "XAUUSD", bars: bars("TGTT", 1, "2026-08-25") },
    AUDUSD: { displayName: "AUDUSD", bars: bars("GGTG", 1, "2026-08-25") },
    USDCAD: { displayName: "USDCAD", bars: bars("TGGT", 1, "2026-08-25") },
    USDJPY: { displayName: "USDJPY", bars: bars("GTGT", 1, "2026-08-25") },
    EURUSD: { displayName: "EURUSD", bars: bars("TGGT", 1, "2026-08-25") },
  } as const;

  assert.equal(backfillSuppressedHistory(state, "2026-08-25", market), 5);
  for (const base of ["GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const) {
    assert.ok(state.days["2026-08-25"].symbols[base]?.alerts.some((alert) => alert.slotHour === 3));
  }
  assert.ok(state.days["2026-08-25"].symbols.XAUUSD?.alerts.some((alert) => alert.slotHour === 4));
  for (const base of ["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const) {
    assert.equal(state.days["2026-08-25"].symbols[base]?.alerts.some((alert) => alert.slotHour === 5), false);
  }
});

test("suppressed migration slots backfill v7 history without replay state loss", () => {
  const state = emptyCloudState();
  state.days["2026-08-21"] = {
    suppressedThroughHour: 6,
    symbols: Object.fromEntries(["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY"].map((base) => [base, { alerts: [], blockedSlots: [] }])),
  };
  const market = {
    GBPUSD: { displayName: "GBPUSD", bars: bars("GGTTG", 1) },
    XAUUSD: { displayName: "XAUUSD", bars: bars("TTTTT", 1) },
    AUDUSD: { displayName: "AUDUSD", bars: bars("GGTTG", 1) },
    USDCAD: { displayName: "USDCAD", bars: bars("TTTGG", 1) },
    USDJPY: { displayName: "USDJPY", bars: bars("GGGTT", 1) },
    EURUSD: { displayName: "EURUSD", bars: bars("GTTGG", 1) },
  } as const;
  const added = backfillSuppressedHistory(state, "2026-08-21", market);
  assert.ok(added > 0);
  assert.equal(state.days["2026-08-21"].suppressedThroughHour, 6);
  assert.equal(backfillSuppressedHistory(state, "2026-08-21", market), 0);
});

test("older signal-rule feeds start a fresh v35 state instead of carrying stale H4/base semantics", () => {
  const legacyV2 = {
    schemaVersion: 7,
    signalRuleVersion: 2,
    profile: "cTrader IcMarkets",
    publishedAt: "2026-08-21T00:00:00Z",
    hours: [3, 4, 5, 6, 7],
    symbols: ["XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"],
    days: {
      "2026-08-21": {
        symbols: {
          XAUUSD: {
            alerts: [{
              slotHour: 4,
              pattern: "T G G",
              patternKind: "sw3Pure",
              bars: ["2026-08-21T03:00", "2026-08-21T02:00", "2026-08-21T01:00"],
              symbol: "XAUUSD",
              profile: "cTrader IcMarkets",
              scannerBase: "AUDUSD",
              scannerSymbol: "AUDUSD",
              baseSymbol: "GBPUSD",
              baseSignal: "BUY",
              baseHour: 3,
              baseDirection: "T",
              signal: "SELL",
              postSignalInverted: true,
              postSignalRule: "fri-cycle",
            }],
          },
        },
      },
    },
  };
  const state = seedCloudStateFromPublic(legacyV2, "2026-08-21", 7);
  assert.equal(state.version, 35);
  assert.equal(state.days["2026-08-21"].suppressedThroughHour, 7);
  assert.deepEqual(state.days["2026-08-21"].symbols.XAUUSD?.alerts, []);
});

test("older public schemas start a fresh suppressed v7 state instead of replaying obsolete semantics", () => {
  const legacy = {
    schemaVersion: 6,
    profile: "cTrader IcMarkets",
    publishedAt: "2026-08-21T00:00:00Z",
    hours: [3, 4, 5],
    symbols: ["XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"],
    days: {},
  };
  const state = seedCloudStateFromPublic(legacy, "2026-08-21", 5);
  assert.equal(state.version, 35);
  assert.equal(state.days["2026-08-21"].suppressedThroughHour, 5);
});

test("public feed v7 excludes H5 under signal rule v29", () => {
  const state = emptyCloudState();
  const match = findH1PatternMatches(bars("GGT", 3), 6).find((item) => item.slotHour === 6)!;
  const alert = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    scannerBase: "XAUUSD",
    scannerSymbol: "XAUUSD",
    match,
    baseSymbol: "GBPUSD",
    baseBar: bars("T", 5)[0],
  });
  state.days["2026-08-21"] = { symbols: { XAUUSD: { alerts: [alert], blockedSlots: [] } } };
  const feed = buildPublicFeed(state, "2026-08-21T00:00:00Z");
  assert.equal(feed.schemaVersion, 7);
  assert.equal(feed.signalRuleVersion, 29);
  assert.deepEqual(feed.hours, [3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]);
  const row = feed.days["2026-08-21"].symbols.XAUUSD?.alerts[0];
  assert.equal(row?.patternKind, "sw3Pure");
  assert.equal(row?.signal, "SELL");
  assert.equal(row?.tradeAllowed, true);
  assert.equal(row?.lookbackPattern, null);
  assert.equal(row?.lookbackAction, "none");
  assert.deepEqual(feed.days["2026-08-21"].symbols.XAUUSD?.blockedSlots, []);
  assert.equal("blockedByPureSlot" in (row || {}), false);
  assert.equal("previousPureSlot" in (row || {}), false);
  assert.equal("postCheckApplied" in (row || {}), false);
  assert.equal("sourceSignal" in (row || {}), false);
});
