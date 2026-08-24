import test from "node:test";
import assert from "node:assert/strict";
import {
  H1_HISTORY_RETENTION_CALENDAR_DAYS,
  H1_POST_SIGNAL_ACTIVE_WEEKDAYS,
  H1_SCAN_END_HOUR,
  H1_SCAN_START_HOUR,
  backfillSuppressedHistory,
  baseSymbolForTarget,
  buildPublicFeed,
  buildStoredAlert,
  buildTelegramMessage,
  configuredPostSignalDecision,
  emptyCloudState,
  findH1PatternMatches,
  postSignalDecision,
  reconcileTradeState,
  scannerBaseForTarget,
  seedCloudStateFromPublic,
  signalFromBaseAfterCalendar,
  signalFromPatternBase,
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

test("scanner emits only H06-H16 and keeps SW3 pattern semantics inside the active window", () => {
  assert.equal(H1_SCAN_START_HOUR, 6);
  assert.equal(H1_SCAN_END_HOUR, 16);

  const pureTgg = findH1PatternMatches(bars("GGT", 3), 18).filter((item) => item.slotHour === 6);
  const pureGtt = findH1PatternMatches(bars("TTG", 3), 18).filter((item) => item.slotHour === 6);
  const normalT = findH1PatternMatches(bars("TTT", 3), 18).filter((item) => item.slotHour === 6);
  const normalG = findH1PatternMatches(bars("GGG", 3), 18).filter((item) => item.slotHour === 6);
  assert.deepEqual(pureTgg.map((item) => [item.pattern.join(""), item.patternKind]), [["TGG", "sw3Pure"]]);
  assert.deepEqual(pureGtt.map((item) => [item.pattern.join(""), item.patternKind]), [["GTT", "sw3Pure"]]);
  assert.deepEqual(normalT.map((item) => [item.pattern.join(""), item.patternKind]), [["TTT", "sw3Normal"]]);
  assert.deepEqual(normalG.map((item) => [item.pattern.join(""), item.patternKind]), [["GGG", "sw3Normal"]]);

  assert.equal(findH1PatternMatches(bars("GGT", 2), 18).some((item) => item.slotHour === 5), false);
  assert.equal(findH1PatternMatches(bars("GGT", 13), 18).some((item) => item.slotHour === 16), true);
  assert.equal(findH1PatternMatches(bars("GGT", 14), 18).some((item) => item.slotHour === 17), false);
  assert.equal(findH1PatternMatches(bars("GT", 1), 18).some((item) => item.patternKind === "sw2"), false);
});

test("normal SW3 guard skips a slot once the same-direction run reaches four or more", () => {
  const t4 = findH1PatternMatches(bars("TTTT"), 5).filter((item) => item.slotHour === 5);
  const g4 = findH1PatternMatches(bars("GGGG"), 5).filter((item) => item.slotHour === 5);
  const t5 = findH1PatternMatches(bars("TTTTT"), 6).filter((item) => item.slotHour === 6);
  assert.deepEqual(t4, []);
  assert.deepEqual(g4, []);
  assert.deepEqual(t5, []);
});

test("every pattern keeps the H1 base before calendar post-signal rules", () => {
  for (const kind of ["sw2", "sw3Pure", "sw3Normal"] as const) {
    assert.equal(signalFromPatternBase("BUY", kind), "BUY");
    assert.equal(signalFromPatternBase("SELL", kind), "SELL");
  }
  for (const slot of [5, 6, 7, 8, 15, 16, 17]) {
    assert.equal(signalFromBaseAfterCalendar("BUY", "2026-08-17", slot), "BUY");
    assert.equal(signalFromBaseAfterCalendar("SELL", "2026-08-17", slot), "SELL");
  }
});

test("target scanner/base mapping is XAUUSD+GBPUSD for XAU and GBPUSD+own-base for every other symbol", () => {
  assert.equal(scannerBaseForTarget("XAUUSD"), "XAUUSD");
  assert.equal(baseSymbolForTarget("XAUUSD"), "GBPUSD");
  for (const base of ["EURUSD", "AUDUSD", "USDCAD", "USDJPY"] as const) {
    assert.equal(scannerBaseForTarget(base), "GBPUSD");
    assert.equal(baseSymbolForTarget(base), base);
  }
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

test("Pattern 1 uses the non-overlapping three-candle lookback from H8 onward", () => {
  const blockedByPattern1 = findH1PatternMatches(bars("GGTGGT", 2), 8).find((item) => item.slotHour === 8)!;
  assert.deepEqual([blockedByPattern1.pattern.join(""), blockedByPattern1.lookbackPattern, blockedByPattern1.lookbackAction, blockedByPattern1.tradeAllowed], ["TGG", "TGG", "block-pattern1", false]);

  const blockedByPattern2 = findH1PatternMatches(bars("TTTGGT", 2), 8).find((item) => item.slotHour === 8)!;
  assert.deepEqual([blockedByPattern2.lookbackPattern, blockedByPattern2.lookbackAction, blockedByPattern2.tradeAllowed], ["TTT", "block-pattern2", false]);

  const invertedByPattern3 = findH1PatternMatches(bars("GTGGGT", 2), 8).find((item) => item.slotHour === 8)!;
  assert.deepEqual([invertedByPattern3.lookbackPattern, invertedByPattern3.lookbackAction, invertedByPattern3.tradeAllowed], ["GTG", "invert-pattern3", true]);

  const beforeH8 = findH1PatternMatches(bars("TTTGGT", 1), 7).find((item) => item.slotHour === 7)!;
  assert.deepEqual([beforeH8.lookbackPattern, beforeH8.lookbackAction, beforeH8.tradeAllowed], [null, "none", true]);
});

test("Pattern 2 is strongest and bypasses allowTrade lookback", () => {
  const match = findH1PatternMatches(bars("TTGTTT", 2), 8).find((item) => item.slotHour === 8)!;
  assert.deepEqual([match.pattern.join(""), match.patternKind, match.lookbackPattern, match.lookbackAction, match.tradeAllowed], ["TTT", "sw3Normal", null, "none", true]);
});

test("Pattern 3 lookback inversion is independent from post-signal inversion", () => {
  const match = findH1PatternMatches(bars("GTGGGT", 2, "2026-08-21"), 8).find((item) => item.slotHour === 8)!;
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
  const allowedMatch = findH1PatternMatches(bars("TTGTTT", 2), 8).find((item) => item.slotHour === 8)!;
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
  assert.match(message, /Logic pattern: giữ nguyên GBPUSD H1/);
  assert.match(message, /Hậu signal: đảo theo chu kỳ Thứ 6 special/);
  assert.match(message, /Signal XAUUSD H1: SELL/);
  assert.doesNotMatch(message, /đã xuất hiện|vẫn tính signal|Hậu kiểm|post-check/i);
});

test("normal SW3 keeps the base before active Friday post-signal inversion", () => {
  const match = findH1PatternMatches(bars("TTT", 3), 6).find((item) => item.slotHour === 6)!;
  const alert = buildStoredAlert({
    base: "EURUSD",
    brokerSymbol: "EURUSD",
    scannerBase: "GBPUSD",
    scannerSymbol: "GBPUSD",
    match,
    baseSymbol: "EURUSD",
    baseBar: bars("G", 5)[0],
  });
  assert.equal(alert.patternKind, "sw3Normal");
  assert.equal(alert.baseH1Signal, "SELL");
  assert.equal(alert.postSignalRule, "fri-cycle");
  assert.equal(alert.symbolH1Signal, "BUY");
  assert.equal("previousPureSlot" in alert, false);
});

test("suppressed migration slots backfill v7 history without replay state loss", () => {
  const state = emptyCloudState();
  state.days["2026-08-21"] = {
    suppressedThroughHour: 6,
    symbols: Object.fromEntries(["XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"].map((base) => [base, { alerts: [], blockedSlots: [] }])),
  };
  const market = {
    GBPUSD: { displayName: "GBPUSD", bars: bars("GGTTG", 1) },
    XAUUSD: { displayName: "XAUUSD", bars: bars("TTTTT", 1) },
    EURUSD: { displayName: "EURUSD", bars: bars("GGGTT", 1) },
    AUDUSD: { displayName: "AUDUSD", bars: bars("GGTTG", 1) },
    USDCAD: { displayName: "USDCAD", bars: bars("TTTGG", 1) },
    USDJPY: { displayName: "USDJPY", bars: bars("GGGTT", 1) },
  } as const;
  const added = backfillSuppressedHistory(state, "2026-08-21", market);
  assert.ok(added > 0);
  assert.equal(state.days["2026-08-21"].suppressedThroughHour, 6);
  assert.equal(backfillSuppressedHistory(state, "2026-08-21", market), 0);
});

test("older signal-rule feeds start a fresh v11 state instead of carrying stale allowTrade semantics", () => {
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
  assert.equal(state.version, 11);
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
  assert.equal(state.version, 11);
  assert.equal(state.days["2026-08-21"].suppressedThroughHour, 5);
});

test("public feed v7 carries allowTrade lookback metadata under signal rule v5", () => {
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
  assert.equal(feed.signalRuleVersion, 5);
  assert.deepEqual(feed.hours, [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]);
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
