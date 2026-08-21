import test from "node:test";
import assert from "node:assert/strict";
import {
  backfillSuppressedHistory,
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

test("XAU/EUR/AUD keep SW2 and reverse SW3 while CAD/JPY reverse SW2 and follow SW3", () => {
  for (const base of ["XAUUSD", "EURUSD", "AUDUSD"] as const) {
    assert.equal(signalFromPatternBase(base, "BUY", "sw2"), "BUY");
    assert.equal(signalFromPatternBase(base, "SELL", "sw2"), "SELL");
    for (const kind of ["sw3Pure", "sw3Normal"] as const) {
      assert.equal(signalFromPatternBase(base, "BUY", kind), "SELL");
      assert.equal(signalFromPatternBase(base, "SELL", kind), "BUY");
    }
  }
  for (const base of ["USDCAD", "USDJPY"] as const) {
    assert.equal(signalFromPatternBase(base, "BUY", "sw2"), "SELL");
    assert.equal(signalFromPatternBase(base, "SELL", "sw2"), "BUY");
    for (const kind of ["sw3Pure", "sw3Normal"] as const) {
      assert.equal(signalFromPatternBase(base, "BUY", kind), "BUY");
      assert.equal(signalFromPatternBase(base, "SELL", kind), "SELL");
    }
  }
});

test("target scanner/base mapping uses own source plus GBPUSD base for CAD and JPY", () => {
  assert.equal(scannerBaseForTarget("XAUUSD"), "AUDUSD");
  assert.equal(baseSymbolForTarget("XAUUSD"), "GBPUSD");
  for (const base of ["EURUSD", "AUDUSD"] as const) {
    assert.equal(scannerBaseForTarget(base), "GBPUSD");
    assert.equal(baseSymbolForTarget(base), base);
  }
  for (const base of ["USDCAD", "USDJPY"] as const) {
    assert.equal(scannerBaseForTarget(base), base);
    assert.equal(baseSymbolForTarget(base), "GBPUSD");
  }
});

test("USDCAD own-source SW2 reverses GBPUSD base and SW3 follows it", () => {
  const sw2Match = findH1PatternMatches(bars("GT"), 3).find((item) => item.slotHour === 3)!;
  const sw2 = buildStoredAlert({
    base: "USDCAD",
    brokerSymbol: "USDCAD",
    scannerBase: "USDCAD",
    scannerSymbol: "USDCAD",
    match: sw2Match,
    baseSymbol: "GBPUSD",
    baseBar: bars("T", 2)[0],
  });
  assert.equal(sw2.baseH1Signal, "BUY");
  assert.equal(sw2.symbolH1Signal, "SELL");

  const pureMatch = findH1PatternMatches(bars("GGT"), 4).find((item) => item.slotHour === 4)!;
  const pure = buildStoredAlert({
    base: "USDCAD",
    brokerSymbol: "USDCAD",
    scannerBase: "USDCAD",
    scannerSymbol: "USDCAD",
    match: pureMatch,
    baseSymbol: "GBPUSD",
    baseBar: bars("T", 3)[0],
  });
  assert.equal(pure.baseH1Signal, "BUY");
  assert.equal(pure.symbolH1Signal, "BUY");
});

test("pure SW3 exactly two slots after an accepted pure is skipped and tracking resets", () => {
  const h4H6 = findH1PatternMatches(bars("GGTTG"), 6).filter((item) => item.patternKind === "sw3Pure");
  assert.deepEqual(h4H6.map((item) => [item.slotHour, item.pattern.join("")]), [[4, "TGG"]]);

  const reset = findH1PatternMatches(bars("GGTTGGT"), 8).filter((item) => item.patternKind === "sw3Pure");
  assert.deepEqual(reset.map((item) => [item.slotHour, item.pattern.join("")]), [
    [4, "TGG"],
    [8, "TGG"],
  ]);

  const h6H8 = findH1PatternMatches(bars("GGTTG", 3), 8).filter((item) => item.patternKind === "sw3Pure");
  assert.deepEqual(h6H8.map((item) => [item.slotHour, item.pattern.join("")]), [[6, "TGG"]]);
});

test("accepted pure SW3 Telegram marks /!\\ with no repeat warning metadata", () => {
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
  const message = buildTelegramMessage("XAUUSD", "2026-08-21", alert);
  assert.match(message, /\/!\\ SW 3 cây thuần/);
  assert.match(message, /Signal XAUUSD H1: SELL/);
  assert.doesNotMatch(message, /đã xuất hiện|vẫn tính signal|Hậu kiểm|post-check/i);
});

test("normal SW3 reverses the target base with no post-check metadata", () => {
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
  assert.equal(alert.symbolH1Signal, "BUY");
  assert.equal("previousPureSlot" in alert, false);
});

test("suppressed migration slots backfill v7 history without replay state loss", () => {
  const state = emptyCloudState();
  state.days["2026-08-21"] = {
    suppressedThroughHour: 6,
    symbols: Object.fromEntries(["XAUUSD", "EURUSD", "AUDUSD", "USDCAD", "USDJPY"].map((base) => [base, { alerts: [] }])),
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
  assert.equal(state.version, 7);
  assert.equal(state.days["2026-08-21"].suppressedThroughHour, 5);
});

test("public feed v7 contains accepted pure signals without repeat metadata", () => {
  const state = emptyCloudState();
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
  state.days["2026-08-21"] = { symbols: { XAUUSD: { alerts: [alert] } } };
  const feed = buildPublicFeed(state, "2026-08-21T00:00:00Z");
  assert.equal(feed.schemaVersion, 7);
  const row = feed.days["2026-08-21"].symbols.XAUUSD?.alerts[0];
  assert.equal(row?.patternKind, "sw3Pure");
  assert.equal(row?.signal, "SELL");
  assert.equal("previousPureSlot" in (row || {}), false);
  assert.equal("postCheckApplied" in (row || {}), false);
  assert.equal("sourceSignal" in (row || {}), false);
});
