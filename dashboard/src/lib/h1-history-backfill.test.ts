import test from "node:test";
import assert from "node:assert/strict";
import { emptyCloudState, type H1Base, type H1Direction, type H1DirectionBar, type H1M15Bar } from "./h1-cloud-scanner.ts";
import { mergeHistoricalBackfill, reconstructHistoricalDays } from "./h1-history-backfill.ts";

function h1Bars(date: string): H1DirectionBar[] {
  return Array.from({ length: 17 }, (_, hour) => ({
    hour,
    brokerDate: date,
    brokerTime: `${date}T${String(hour).padStart(2, "0")}:00`,
    direction: "T" as H1Direction,
  }));
}

function m15Bars(date: string, direction: H1Direction = "T"): H1M15Bar[] {
  return Array.from({ length: 68 }, (_, index) => {
    const minuteOfDay = 15 * index;
    return {
      brokerDate: date,
      brokerTime: `${date}T${String(Math.floor(minuteOfDay / 60)).padStart(2, "0")}:${String(minuteOfDay % 60).padStart(2, "0")}`,
      minuteOfDay,
      direction,
    };
  });
}

function marketForDates(...dates: string[]) {
  const bases: H1Base[] = ["GBPUSD", "XAUUSD", "AUDUSD", "USDCAD", "USDJPY", "EURUSD"];
  return Object.fromEntries(bases.map((base) => [base, {
    displayName: base,
    bars: dates.flatMap((date) => h1Bars(date)),
    m15Bars: dates.flatMap((date) => m15Bars(date)),
  }])) as Record<H1Base, { displayName: string; bars: H1DirectionBar[]; m15Bars: H1M15Bar[] }>;
}

test("historical reconstruction applies the block schedule, M15 engine and XAU cycle", () => {
  const history = reconstructHistoricalDays(marketForDates("2026-07-06", "2026-07-04"));
  // Weekend broker dates are never reconstructed.
  assert.ok(history["2026-07-06"]);
  assert.equal(history["2026-07-04"], undefined);

  const gold = history["2026-07-06"].symbols.XAUUSD?.alerts ?? [];
  const fx = history["2026-07-06"].symbols.GBPUSD?.alerts ?? [];
  // XAUUSD owns H4 and joins every later block; FX starts at H3 and skips H4.
  assert.deepEqual(gold.map((alert) => alert.slotHour), [4, 6, 9, 12, 14, 16]);
  assert.deepEqual(fx.map((alert) => alert.slotHour), [3, 6, 9, 12, 14, 16]);

  // All-T M15 extends every window to Pattern 5. Pattern 5 inverts its
  // post-block H:15 BUY base and enters two hours after the block.
  for (const alert of [...gold, ...fx]) {
    assert.equal(alert.patternKind, "pattern5");
    assert.equal(alert.m15PairInverted, true);
    assert.equal(alert.entryOffsetMinutes, 120);
    assert.equal(alert.baseSymbol, alert.symbol === "XAUUSD" ? "XAUUSD" : "GBPUSD");
  }
  assert.deepEqual(gold.map((alert) => alert.entryTime), ["06:00", "08:00", "11:00", "14:00", "16:00", "18:00"]);

  // Pattern 5 first flips BUY to SELL. Mon 2026-07-06 then applies the XAU
  // special-cycle inversion once more, while FX stays at SELL.
  assert.ok(gold.every((alert) => alert.postSignalRule === "mon-cycle" && alert.symbolH1Signal === "BUY"));
  assert.ok(fx.every((alert) => alert.postSignalRule === "none" && alert.symbolH1Signal === "SELL"));
});

test("historical days without M15 coverage yield no alerts instead of wrong signals", () => {
  const market = marketForDates("2026-07-06");
  const withoutM15 = Object.fromEntries(Object.entries(market).map(([base, item]) => [base, {
    displayName: item.displayName,
    bars: item.bars,
    m15Bars: [],
  }])) as unknown as typeof market;
  const history = reconstructHistoricalDays(withoutM15);
  for (const symbolState of Object.values(history["2026-07-06"].symbols)) {
    assert.deepEqual(symbolState?.alerts, []);
  }
});

test("backfill merge can restore a missing current day after the scanner window without overwriting an existing live day", () => {
  const reconstructed = reconstructHistoricalDays(marketForDates("2026-07-03", "2026-07-06"));
  const missingCurrent = emptyCloudState();
  const recovered = mergeHistoricalBackfill(missingCurrent, reconstructed, "2026-07-06", { includeMissingCurrentDay: true });
  assert.ok(recovered.addedDays >= 2);
  assert.ok(missingCurrent.days["2026-07-06"]);
  assert.ok(Object.values(missingCurrent.days["2026-07-06"].symbols).some((symbol) => (symbol?.alerts.length || 0) > 0));

  const existingLive = emptyCloudState();
  existingLive.days["2026-07-06"] = {
    symbols: {
      XAUUSD: {
        alerts: [{ ...structuredClone(reconstructed["2026-07-06"].symbols.XAUUSD!.alerts[0]), symbol: "LIVE-SENTINEL" }],
      },
    },
  };
  mergeHistoricalBackfill(existingLive, reconstructed, "2026-07-06", { includeMissingCurrentDay: true });
  assert.equal(existingLive.days["2026-07-06"].symbols.XAUUSD!.alerts[0].symbol, "LIVE-SENTINEL");
});

test("backfill merge is idempotent, preserves existing rows and never overwrites current live day", () => {
  const reconstructed = reconstructHistoricalDays(marketForDates("2026-07-03", "2026-07-06"));
  const state = emptyCloudState();
  const historicalDay = reconstructed["2026-07-03"];
  const original = structuredClone(historicalDay.symbols.XAUUSD!.alerts[0]);
  original.symbolH1Signal = original.symbolH1Signal === "BUY" ? "SELL" : "BUY";
  state.days["2026-07-03"] = { symbols: { XAUUSD: { alerts: [original] } } };
  state.days["2026-07-06"] = { symbols: { XAUUSD: { alerts: [{ ...reconstructed["2026-07-06"].symbols.XAUUSD!.alerts[0], symbol: "LIVE-SENTINEL" }] } } };

  const first = mergeHistoricalBackfill(state, reconstructed, "2026-07-06");
  assert.ok(first.addedAlerts > 0);
  assert.equal(state.days["2026-07-03"].symbols.XAUUSD!.alerts.find((alert) => alert.slotHour === original.slotHour)!.symbolH1Signal, original.symbolH1Signal);
  assert.equal(state.days["2026-07-06"].symbols.XAUUSD!.alerts[0].symbol, "LIVE-SENTINEL");
  const afterFirst = JSON.stringify(state);

  const second = mergeHistoricalBackfill(state, reconstructed, "2026-07-06");
  assert.deepEqual(second, { addedDays: 0, addedAlerts: 0 });
  assert.equal(JSON.stringify(state), afterFirst);
});
