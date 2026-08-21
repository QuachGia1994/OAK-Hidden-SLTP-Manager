import test from "node:test";
import assert from "node:assert/strict";
import {
  baseSymbolForTarget,
  buildPublicFeed,
  buildStoredAlert,
  buildTelegramMessage,
  emptyCloudState,
  findH1PatternMatches,
  scannerBaseForTarget,
  seedCloudStateFromPublic,
  signalFromPatternBase,
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

test("only pure SW3 reverses the H1 base signal", () => {
  for (const kind of ["sw2", "sw3Alternating", "sw4Alternating"] as const) {
    assert.equal(signalFromPatternBase("BUY", kind), "BUY");
    assert.equal(signalFromPatternBase("SELL", kind), "SELL");
  }
  assert.equal(signalFromPatternBase("BUY", "sw3Pure"), "SELL");
  assert.equal(signalFromPatternBase("SELL", "sw3Pure"), "BUY");
});

test("pattern scanners are AUDUSD for XAU and GBPUSD for every other target", () => {
  assert.equal(scannerBaseForTarget("XAUUSD"), "AUDUSD");
  assert.equal(baseSymbolForTarget("XAUUSD"), "GBPUSD");
  for (const base of ["EURUSD", "AUDUSD", "USDCAD", "USDJPY"] as const) {
    assert.equal(scannerBaseForTarget(base), "GBPUSD");
    assert.equal(baseSymbolForTarget(base), base);
  }
});

test("SW2 is H03-only from H02 + H01", () => {
  const h3 = findH1PatternMatches(bars("GT"), 3);
  assert.deepEqual(h3.map((item) => [item.slotHour, item.pattern.join(""), item.patternKind]), [
    [3, "TG", "sw2"],
  ]);
  const h4 = findH1PatternMatches(bars("GGT"), 4);
  assert.equal(h4.some((item) => item.slotHour === 4 && item.patternKind === "sw2"), false);
});

test("pure SW3 is only TGG or GTT", () => {
  const tgg = findH1PatternMatches(bars("GGT"), 4).filter((item) => item.slotHour === 4);
  const gtt = findH1PatternMatches(bars("TTG"), 4).filter((item) => item.slotHour === 4);
  assert.deepEqual(tgg.map((item) => [item.pattern.join(""), item.patternKind]), [["TGG", "sw3Pure"]]);
  assert.deepEqual(gtt.map((item) => [item.pattern.join(""), item.patternKind]), [["GTT", "sw3Pure"]]);
});

test("alternating SW3 emits TGT or GTG", () => {
  const matches = findH1PatternMatches(bars("TGT"), 4).filter((item) => item.slotHour === 4);
  assert.deepEqual(matches.map((item) => [item.pattern.join(""), item.patternKind]), [["TGT", "sw3Alternating"]]);
});

test("alternating SW4 emits TGTG or GTGT and wins at the current slot", () => {
  const t = findH1PatternMatches(bars("GTGT"), 5).filter((item) => item.slotHour === 5);
  const g = findH1PatternMatches(bars("TGTG"), 5).filter((item) => item.slotHour === 5);
  assert.deepEqual(t.map((item) => [item.pattern.join(""), item.patternKind]), [["TGTG", "sw4Alternating"]]);
  assert.deepEqual(g.map((item) => [item.pattern.join(""), item.patternKind]), [["GTGT", "sw4Alternating"]]);
});

test("XAU signal uses AUDUSD scanner plus GBPUSD H1 base", () => {
  const match = findH1PatternMatches(bars("TGT"), 4).find((item) => item.slotHour === 4)!;
  const alert = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAU/USD",
    scannerBase: "AUDUSD",
    scannerSymbol: "AUD/USD",
    match,
    baseSymbol: "GBPUSD",
    baseBar: bars("T", 3)[0],
  });
  assert.equal(alert.patternKind, "sw3Alternating");
  assert.equal(alert.baseH1Signal, "BUY");
  assert.equal(alert.symbolH1Signal, "BUY");
  assert.match(buildTelegramMessage("XAUUSD", "2026-08-21", alert), /giữ nguyên GBPUSD H1/);
});

test("XAU pure SW3 reverses GBPUSD H1 base", () => {
  const match = findH1PatternMatches(bars("GGT"), 4).find((item) => item.slotHour === 4)!;
  const alert = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    scannerBase: "AUDUSD",
    scannerSymbol: "AUDUSD",
    match,
    baseSymbol: "GBPUSD",
    baseBar: bars("T", 3)[0],
  });
  assert.equal(alert.patternKind, "sw3Pure");
  assert.equal(alert.baseH1Signal, "BUY");
  assert.equal(alert.symbolH1Signal, "SELL");
});

test("other symbols use GBPUSD scanner plus their own H1 base", () => {
  const match = findH1PatternMatches(bars("GTGT"), 5).find((item) => item.slotHour === 5)!;
  const alert = buildStoredAlert({
    base: "EURUSD",
    brokerSymbol: "EURUSD",
    scannerBase: "GBPUSD",
    scannerSymbol: "GBPUSD",
    match,
    baseSymbol: "EURUSD",
    baseBar: bars("G", 4)[0],
  });
  assert.equal(alert.patternKind, "sw4Alternating");
  assert.equal(alert.baseH1Signal, "SELL");
  assert.equal(alert.symbolH1Signal, "SELL");
});

test("older feeds suppress pre-cutover slots instead of replaying obsolete semantics", () => {
  const legacy = {
    schemaVersion: 5,
    profile: "cTrader IcMarkets",
    publishedAt: "2026-08-21T00:00:00Z",
    hours: [3, 4, 5],
    symbols: ["XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"],
    days: {},
  };
  const state = seedCloudStateFromPublic(legacy, "2026-08-21", 5);
  assert.equal(state.version, 6);
  assert.equal(state.days["2026-08-21"].suppressedThroughHour, 5);
  assert.deepEqual(state.days["2026-08-21"].symbols.XAUUSD?.alerts, []);
});

test("public feed v6 contains only scanner/base/final-signal semantics", () => {
  const state = emptyCloudState();
  const match = findH1PatternMatches(bars("GT"), 3)[0];
  const alert = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    scannerBase: "AUDUSD",
    scannerSymbol: "AUDUSD",
    match,
    baseSymbol: "GBPUSD",
    baseBar: bars("T", 2)[0],
  });
  state.days["2026-08-21"] = { symbols: { XAUUSD: { alerts: [alert] } } };
  const feed = buildPublicFeed(state, "2026-08-21T00:00:00Z");
  assert.equal(feed.schemaVersion, 6);
  assert.equal(feed.profile, "cTrader IcMarkets");
  const row = feed.days["2026-08-21"].symbols.XAUUSD?.alerts[0];
  assert.equal(row?.scannerBase, "AUDUSD");
  assert.equal(row?.baseSymbol, "GBPUSD");
  assert.equal(row?.baseSignal, "BUY");
  assert.equal(row?.signal, "BUY");
  assert.equal("targetPattern" in (row || {}), false);
  assert.equal("warningKind" in (row || {}), false);
});
