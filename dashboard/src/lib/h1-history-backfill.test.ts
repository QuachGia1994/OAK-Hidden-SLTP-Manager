import test from "node:test";
import assert from "node:assert/strict";
import { audusdH3SignalForXauH4, buildStoredAlert, emptyCloudState, findH1PatternMatchesForTarget, type H1Base, type H1Direction, type H1DirectionBar } from "./h1-cloud-scanner.ts";
import { mergeHistoricalBackfill, reconstructHistoricalDays } from "./h1-history-backfill.ts";

function bars(sequenceOldestToNewest: string, date: string, startHour = 1): H1DirectionBar[] {
  return [...sequenceOldestToNewest].map((direction, index) => {
    const hour = startHour + index;
    return { hour, brokerDate: date, brokerTime: `${date}T${String(hour).padStart(2, "0")}:00`, direction: direction as H1Direction };
  });
}

function marketForDates(...dates: string[]) {
  const sequences: Record<H1Base, string> = {
    GBPUSD: "GGTGGT",
    XAUUSD: "TTGGTT",
    AUDUSD: "GGTGGT",
    USDCAD: "TTTGGG",
    USDJPY: "GGGTTT",
    EURUSD: "GTGTTG",
  };
  return Object.fromEntries((Object.keys(sequences) as H1Base[]).map((base) => [base, {
    displayName: base,
    bars: dates.flatMap((date) => bars(sequences[base], date)),
  }])) as Record<H1Base, { displayName: string; bars: H1DirectionBar[] }>;
}

test("historical reconstruction reuses live pattern/base/calendar rules and skips weekend records", () => {
  const history = reconstructHistoricalDays(marketForDates("2026-08-21", "2026-08-22"));
  assert.ok(history["2026-08-21"]);
  assert.equal(history["2026-08-22"], undefined);

  const scannerBars = marketForDates("2026-08-21").XAUUSD.bars;
  const liveMatch = findH1PatternMatchesForTarget("XAUUSD", scannerBars, 18).find((item) => item.slotHour === 6)!;
  const liveExpected = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    scannerBase: "XAUUSD",
    scannerSymbol: "XAUUSD",
    match: liveMatch,
    baseSymbol: "GBPUSD",
    baseBar: marketForDates("2026-08-21").GBPUSD.bars.find((bar) => bar.hour === 5)!,
  });
  const historical = history["2026-08-21"].symbols.XAUUSD?.alerts.find((alert) => alert.slotHour === 6);
  assert.deepEqual(historical, liveExpected);

  const market = marketForDates("2026-08-21");
  const xauH4Match = findH1PatternMatchesForTarget("XAUUSD", market.XAUUSD.bars, 4).find((item) => item.slotHour === 4)!;
  const audusdH3Signal = audusdH3SignalForXauH4(market.AUDUSD.bars, market.XAUUSD.bars)!;
  const xauH4Expected = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    scannerBase: "XAUUSD",
    scannerSymbol: "XAUUSD",
    match: xauH4Match,
    baseSymbol: "AUDUSD",
    baseBar: market.AUDUSD.bars.find((bar) => bar.hour === 3)!,
    inheritedSignal: audusdH3Signal,
  });
  const historicalH4 = history["2026-08-21"].symbols.XAUUSD?.alerts.find((alert) => alert.slotHour === 4);
  assert.deepEqual(historicalH4, xauH4Expected);
  assert.deepEqual([historicalH4?.baseSymbol, historicalH4?.baseHour, historicalH4?.baseH1Signal, historicalH4?.symbolH1Signal], ["AUDUSD", 3, audusdH3Signal, audusdH3Signal]);

  const gbpH3Match = findH1PatternMatchesForTarget("GBPUSD", market.GBPUSD.bars, 3).find((item) => item.slotHour === 3)!;
  const gbpH3Expected = buildStoredAlert({
    base: "GBPUSD",
    brokerSymbol: "GBPUSD",
    scannerBase: "GBPUSD",
    scannerSymbol: "GBPUSD",
    match: gbpH3Match,
    baseSymbol: "EURUSD",
    baseBar: market.EURUSD.bars.find((bar) => bar.hour === 2)!,
  });
  assert.deepEqual(history["2026-08-21"].symbols.GBPUSD?.alerts.find((alert) => alert.slotHour === 3), gbpH3Expected);

  const audH3Match = findH1PatternMatchesForTarget("AUDUSD", market.AUDUSD.bars, 3).find((item) => item.slotHour === 3)!;
  const audH3Expected = buildStoredAlert({
    base: "AUDUSD",
    brokerSymbol: "AUDUSD",
    scannerBase: "AUDUSD",
    scannerSymbol: "AUDUSD",
    match: audH3Match,
    baseSymbol: "XAUUSD",
    baseBar: market.XAUUSD.bars.find((bar) => bar.hour === 2)!,
  });
  assert.deepEqual(history["2026-08-21"].symbols.AUDUSD?.alerts.find((alert) => alert.slotHour === 3), audH3Expected);

  const cadH3Match = findH1PatternMatchesForTarget("USDCAD", market.USDCAD.bars, 3).find((item) => item.slotHour === 3)!;
  const cadH3Expected = buildStoredAlert({
    base: "USDCAD",
    brokerSymbol: "USDCAD",
    scannerBase: "USDCAD",
    scannerSymbol: "USDCAD",
    match: cadH3Match,
    baseSymbol: "GBPUSD",
    baseBar: market.GBPUSD.bars.find((bar) => bar.hour === 2)!,
  });
  assert.deepEqual(history["2026-08-21"].symbols.USDCAD?.alerts.find((alert) => alert.slotHour === 3), cadH3Expected);

  const jpyH3Match = findH1PatternMatchesForTarget("USDJPY", market.USDJPY.bars, 3).find((item) => item.slotHour === 3)!;
  const jpyH3Expected = buildStoredAlert({
    base: "USDJPY",
    brokerSymbol: "USDJPY",
    scannerBase: "USDJPY",
    scannerSymbol: "USDJPY",
    match: jpyH3Match,
    baseSymbol: "USDCAD",
    baseBar: market.USDCAD.bars.find((bar) => bar.hour === 2)!,
  });
  assert.deepEqual(history["2026-08-21"].symbols.USDJPY?.alerts.find((alert) => alert.slotHour === 3), jpyH3Expected);

  for (const symbol of ["GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const) {
    assert.equal(history["2026-08-21"].symbols[symbol]?.alerts.some((alert) => alert.slotHour === 4), false);
  }
  for (const symbol of ["XAUUSD", "GBPUSD", "AUDUSD", "USDCAD", "USDJPY"] as const) {
    assert.equal(history["2026-08-21"].symbols[symbol]?.alerts.some((alert) => alert.slotHour === 5), false);
  }
});

test("backfill merge is idempotent, preserves existing rows and never overwrites current live day", () => {
  const reconstructed = reconstructHistoricalDays(marketForDates("2026-08-20", "2026-08-21"));
  const state = emptyCloudState();
  const historicalDay = reconstructed["2026-08-20"];
  const original = structuredClone(historicalDay.symbols.XAUUSD!.alerts[0]);
  original.symbolH1Signal = original.symbolH1Signal === "BUY" ? "SELL" : "BUY";
  state.days["2026-08-20"] = { symbols: { XAUUSD: { alerts: [original], blockedSlots: [] } } };
  state.days["2026-08-21"] = { symbols: { XAUUSD: { alerts: [{ ...reconstructed["2026-08-21"].symbols.XAUUSD!.alerts[0], symbol: "LIVE-SENTINEL" }], blockedSlots: [] } } };

  const first = mergeHistoricalBackfill(state, reconstructed, "2026-08-21");
  assert.ok(first.addedAlerts > 0);
  assert.equal(state.days["2026-08-20"].symbols.XAUUSD!.alerts.find((alert) => alert.slotHour === original.slotHour)!.symbolH1Signal, original.symbolH1Signal);
  assert.equal(state.days["2026-08-21"].symbols.XAUUSD!.alerts[0].symbol, "LIVE-SENTINEL");
  const afterFirst = JSON.stringify(state);

  const second = mergeHistoricalBackfill(state, reconstructed, "2026-08-21");
  assert.deepEqual(second, { addedDays: 0, addedAlerts: 0 });
  assert.equal(JSON.stringify(state), afterFirst);
});
