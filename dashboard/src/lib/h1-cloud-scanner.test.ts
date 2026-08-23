import test from "node:test";
import assert from "node:assert/strict";
import {
  H1_HISTORY_RETENTION_CALENDAR_DAYS,
  H1_POST_SIGNAL_ACTIVE_WEEKDAYS,
  backfillSuppressedHistory,
  baseSymbolForTarget,
  buildPublicFeed,
  buildStoredAlert,
  buildTelegramMessage,
  configuredPostSignalDecision,
  emptyCloudState,
  findH1PatternMatches,
  postSignalDecision,
  pureCooldownSlots,
  reconcilePureCooldownState,
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

test("source scanner has exactly SW2, pure SW3 and normal SW3", () => {
  const sw2 = findH1PatternMatches(bars("GT"), 3).filter((item) => item.slotHour === 3);
  const pureTgg = findH1PatternMatches(bars("GGT"), 4).filter((item) => item.slotHour === 4);
  const pureGtt = findH1PatternMatches(bars("TTG"), 4).filter((item) => item.slotHour === 4);
  const normalT = findH1PatternMatches(bars("TTT"), 4).filter((item) => item.slotHour === 4);
  const normalG = findH1PatternMatches(bars("GGG"), 4).filter((item) => item.slotHour === 4);
  assert.deepEqual(sw2.map((item) => [item.pattern.join(""), item.patternKind]), [["TG", "sw2"]]);
  assert.deepEqual(pureTgg.map((item) => [item.pattern.join(""), item.patternKind]), [["TGG", "sw3Pure"]]);
  assert.deepEqual(pureGtt.map((item) => [item.pattern.join(""), item.patternKind]), [["GTT", "sw3Pure"]]);
  assert.deepEqual(normalT.map((item) => [item.pattern.join(""), item.patternKind]), [["TTT", "sw3Normal"]]);
  assert.deepEqual(normalG.map((item) => [item.pattern.join(""), item.patternKind]), [["GGG", "sw3Normal"]]);
  assert.equal(findH1PatternMatches(bars("TGT"), 4).some((item) => item.slotHour === 4), false);
  assert.equal(findH1PatternMatches(bars("GTG"), 4).some((item) => item.slotHour === 4), false);
});

test("SW2 remains the opening H03 class only", () => {
  const matches = findH1PatternMatches(bars("GGT"), 4);
  assert.equal(matches.some((item) => item.slotHour === 4 && item.patternKind === "sw2"), false);
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

test("pure cooldown blocks only pure matches while normal SW remains tradable", () => {
  const matches = findH1PatternMatches(bars("GGTTGGT"), 8);
  const pure = matches.filter((item) => item.patternKind === "sw3Pure");
  assert.deepEqual(pure.map((item) => [item.slotHour, item.pattern.join(""), item.tradeAllowed, item.blockedByPureSlot]), [
    [4, "TGG", true, null],
    [6, "GTT", false, 4],
    [8, "TGG", true, null],
  ]);
  assert.deepEqual(pureCooldownSlots(matches, 8), [6]);

  const h12PureWindow = findH1PatternMatches(bars("GGTTGGT", 9), 16);
  assert.deepEqual(pureCooldownSlots(h12PureWindow, 16), [14]);
  const h14Pure = h12PureWindow.find((item) => item.slotHour === 14 && item.patternKind === "sw3Pure");
  const h16Pure = h12PureWindow.find((item) => item.slotHour === 16 && item.patternKind === "sw3Pure");
  assert.deepEqual([h14Pure?.tradeAllowed, h14Pure?.blockedByPureSlot], [false, 12]);
  assert.deepEqual([h16Pure?.tradeAllowed, h16Pure?.blockedByPureSlot], [true, null]);

  const normalInsideWindow = findH1PatternMatches(bars("GGTTTG", 9), 15);
  const h14Normal = normalInsideWindow.find((item) => item.slotHour === 14 && item.patternKind === "sw3Normal");
  const h15Pure = normalInsideWindow.find((item) => item.slotHour === 15 && item.patternKind === "sw3Pure");
  assert.deepEqual([h14Normal?.tradeAllowed, h14Normal?.blockedByPureSlot], [true, null]);
  assert.deepEqual([h15Pure?.tradeAllowed, h15Pure?.blockedByPureSlot], [false, 12]);
  assert.deepEqual(pureCooldownSlots(normalInsideWindow, 15), [15]);
});

test("stored H12-H15 rows reconcile stale pure cooldown state before delivered-slot skip", () => {
  const matches = findH1PatternMatches(bars("GGTTTG", 9), 15).filter((item) => [12, 14, 15].includes(item.slotHour));
  const alerts = matches.map((match) => buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    scannerBase: "XAUUSD",
    scannerSymbol: "XAUUSD",
    match,
    baseSymbol: "GBPUSD",
    baseBar: bars("T", match.slotHour - 1)[0],
  }));
  const h14 = alerts.find((alert) => alert.slotHour === 14)!;
  const h15 = alerts.find((alert) => alert.slotHour === 15)!;
  h14.tradeAllowed = false;
  h14.blockedByPureSlot = 12;
  h15.tradeAllowed = true;
  h15.blockedByPureSlot = null;
  const symbolState = { alerts, blockedSlots: [13, 14, 15] };

  assert.equal(reconcilePureCooldownState(symbolState), true);
  assert.deepEqual(alerts.map((alert) => [alert.slotHour, alert.patternKind, alert.tradeAllowed, alert.blockedByPureSlot]), [
    [12, "sw3Pure", true, null],
    [14, "sw3Normal", true, null],
    [15, "sw3Pure", false, 12],
  ]);
  assert.deepEqual(symbolState.blockedSlots, [15]);
  assert.equal(reconcilePureCooldownState(symbolState), false);
});

test("accepted pure SW3 Telegram marks /!\\ with no repeat warning metadata", () => {
  const match = findH1PatternMatches(bars("GGT"), 4).find((item) => item.slotHour === 4)!;
  const alert = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    scannerBase: "XAUUSD",
    scannerSymbol: "XAUUSD",
    match,
    baseSymbol: "GBPUSD",
    baseBar: bars("T", 3)[0],
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
  const match = findH1PatternMatches(bars("TTT"), 4).find((item) => item.slotHour === 4)!;
  const alert = buildStoredAlert({
    base: "EURUSD",
    brokerSymbol: "EURUSD",
    scannerBase: "GBPUSD",
    scannerSymbol: "GBPUSD",
    match,
    baseSymbol: "EURUSD",
    baseBar: bars("G", 3)[0],
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

test("rule-v2 schema7 feed migrates to v10 without inventing blocked slots", () => {
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
  assert.equal(state.version, 10);
  assert.equal(state.days["2026-08-21"].suppressedThroughHour, undefined);
  assert.deepEqual(state.days["2026-08-21"].symbols.XAUUSD?.blockedSlots, []);
  assert.equal(state.days["2026-08-21"].symbols.XAUUSD?.alerts[0]?.tradeAllowed, true);
});

test("rule-v3 feed migration removes generic cooldown blocks and restores normal SW trading", () => {
  const row = (slotHour: number, pattern: string, patternKind: "sw3Pure" | "sw3Normal", tradeAllowed: boolean, blockedByPureSlot: number | null) => ({
    slotHour,
    pattern,
    patternKind,
    bars: [],
    symbol: "XAUUSD",
    profile: "cTrader IcMarkets",
    scannerBase: "AUDUSD" as const,
    scannerSymbol: "AUDUSD",
    baseSymbol: "GBPUSD",
    baseSignal: "BUY" as const,
    baseHour: slotHour - 1,
    baseDirection: "T" as const,
    signal: "BUY" as const,
    postSignalInverted: false,
    postSignalRule: "none" as const,
    tradeAllowed,
    blockedByPureSlot,
  });
  const legacyV3 = {
    schemaVersion: 7,
    signalRuleVersion: 3,
    profile: "cTrader IcMarkets",
    publishedAt: "2026-08-21T00:00:00Z",
    hours: Array.from({ length: 15 }, (_, index) => index + 3),
    symbols: ["XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"],
    days: {
      "2026-08-21": {
        symbols: {
          XAUUSD: {
            alerts: [
              row(12, "T G G", "sw3Pure", true, null),
              row(14, "T T T", "sw3Normal", false, 12),
              row(15, "G T T", "sw3Pure", false, 12),
            ],
            blockedSlots: [13, 14, 15],
          },
        },
      },
    },
  };
  const state = seedCloudStateFromPublic(legacyV3, "2026-08-21", 15);
  const xau = state.days["2026-08-21"].symbols.XAUUSD;
  const h14 = xau?.alerts.find((alert) => alert.slotHour === 14);
  const h15 = xau?.alerts.find((alert) => alert.slotHour === 15);
  assert.equal(state.version, 10);
  assert.deepEqual([h14?.tradeAllowed, h14?.blockedByPureSlot], [true, null]);
  assert.deepEqual([h15?.tradeAllowed, h15?.blockedByPureSlot], [false, 12]);
  assert.deepEqual(xau?.blockedSlots, [15]);
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
  assert.equal(state.version, 10);
  assert.equal(state.days["2026-08-21"].suppressedThroughHour, 5);
});

test("public feed v7 carries pure cooldown trade metadata without changing transport schema", () => {
  const state = emptyCloudState();
  const match = findH1PatternMatches(bars("GGT"), 4).find((item) => item.slotHour === 4)!;
  const alert = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    scannerBase: "XAUUSD",
    scannerSymbol: "XAUUSD",
    match,
    baseSymbol: "GBPUSD",
    baseBar: bars("T", 3)[0],
  });
  state.days["2026-08-21"] = { symbols: { XAUUSD: { alerts: [alert], blockedSlots: [] } } };
  const feed = buildPublicFeed(state, "2026-08-21T00:00:00Z");
  assert.equal(feed.schemaVersion, 7);
  assert.equal(feed.signalRuleVersion, 4);
  const row = feed.days["2026-08-21"].symbols.XAUUSD?.alerts[0];
  assert.equal(row?.patternKind, "sw3Pure");
  assert.equal(row?.signal, "SELL");
  assert.equal(row?.tradeAllowed, true);
  assert.equal(row?.blockedByPureSlot, null);
  assert.deepEqual(feed.days["2026-08-21"].symbols.XAUUSD?.blockedSlots, []);
  assert.equal("previousPureSlot" in (row || {}), false);
  assert.equal("postCheckApplied" in (row || {}), false);
  assert.equal("sourceSignal" in (row || {}), false);
});
