import test from "node:test";
import assert from "node:assert/strict";
import { buildStoredAlert, emptyCloudState, findH1PatternMatchesForTarget, type H1Base, type H1Direction, type H1DirectionBar } from "./h1-cloud-scanner.ts";
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
    EURUSD: "GGGTTT",
    AUDUSD: "GGTGGT",
    USDCAD: "TTTGGG",
    USDJPY: "GGGTTT",
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
  const xauH4Expected = buildStoredAlert({
    base: "XAUUSD",
    brokerSymbol: "XAUUSD",
    scannerBase: "XAUUSD",
    scannerSymbol: "XAUUSD",
    match: xauH4Match,
    baseSymbol: "GBPUSD",
    baseBar: market.GBPUSD.bars.find((bar) => bar.hour === 3)!,
  });
  assert.deepEqual(history["2026-08-21"].symbols.XAUUSD?.alerts.find((alert) => alert.slotHour === 4), xauH4Expected);

  const eurH3Match = findH1PatternMatchesForTarget("EURUSD", market.GBPUSD.bars, 3).find((item) => item.slotHour === 3)!;
  const eurH3Expected = buildStoredAlert({
    base: "EURUSD",
    brokerSymbol: "EURUSD",
    scannerBase: "GBPUSD",
    scannerSymbol: "GBPUSD",
    match: eurH3Match,
    baseSymbol: "EURUSD",
    baseBar: market.EURUSD.bars.find((bar) => bar.hour === 2)!,
  });
  assert.deepEqual(history["2026-08-21"].symbols.EURUSD?.alerts.find((alert) => alert.slotHour === 3), eurH3Expected);

  const fxH5Market = marketForDates("2026-08-21");
  fxH5Market.GBPUSD.bars = bars("GTTT", "2026-08-21");
  const fxH5History = reconstructHistoricalDays(fxH5Market);
  const eurH5Match = findH1PatternMatchesForTarget("EURUSD", fxH5Market.GBPUSD.bars, 5).find((item) => item.slotHour === 5)!;
  const eurH5Expected = buildStoredAlert({
    base: "EURUSD",
    brokerSymbol: "EURUSD",
    scannerBase: "GBPUSD",
    scannerSymbol: "GBPUSD",
    match: eurH5Match,
    baseSymbol: "EURUSD",
    baseBar: fxH5Market.EURUSD.bars.find((bar) => bar.hour === 4)!,
  });
  assert.deepEqual(fxH5History["2026-08-21"].symbols.EURUSD?.alerts.find((alert) => alert.slotHour === 5), eurH5Expected);
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
