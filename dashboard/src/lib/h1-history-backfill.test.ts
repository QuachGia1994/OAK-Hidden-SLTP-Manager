import test from "node:test";
import assert from "node:assert/strict";
import { emptyCloudState, type H1Base, type H1Direction, type H1DirectionBar } from "./h1-cloud-scanner.ts";
import { mergeHistoricalBackfill, reconstructHistoricalDays } from "./h1-history-backfill.ts";

function h1Bars(date: string): H1DirectionBar[] {
  return Array.from({ length: 18 }, (_, hour) => ({
    hour,
    brokerDate: date,
    brokerTime: `${date}T${String(hour).padStart(2, "0")}:00`,
    direction: "T" as H1Direction,
  }));
}

function marketForDates(...dates: string[]) {
  const bases: H1Base[] = ["GBPUSD", "XAUUSD", "AUDUSD", "USDCAD", "USDJPY", "EURUSD"];
  return Object.fromEntries(bases.map((base) => [base, {
    displayName: base,
    bars: dates.flatMap((date) => h1Bars(date)),
  }])) as Record<H1Base, { displayName: string; bars: H1DirectionBar[] }>;
}

test("historical reconstruction applies the block schedule, H1 base and XAU cycle", () => {
  const history = reconstructHistoricalDays(marketForDates("2026-07-06", "2026-07-04"));
  // Weekend broker dates are never reconstructed.
  assert.ok(history["2026-07-06"]);
  assert.equal(history["2026-07-04"], undefined);

  const gold = history["2026-07-06"].symbols.XAUUSD?.alerts ?? [];
  const fx = history["2026-07-06"].symbols.GBPUSD?.alerts ?? [];
  // XAUUSD owns H4 and joins every later block; FX starts at H3 and skips H4.
  assert.deepEqual(gold.map((alert) => alert.slotHour), [4, 6, 9, 12, 14, 16]);
  assert.deepEqual(fx.map((alert) => alert.slotHour), [3, 6, 9, 12, 14, 16]);

  // All-T H1 candles give BUY base on every slot. July cycle Monday row is
  // C N N C C C: keep H3/H4, invert H6/H9, keep H12/H14/H16.
  for (const alert of [...gold, ...fx]) {
    assert.equal(alert.baseH1Signal, "BUY");
    assert.equal(alert.symbol, alert.baseSymbol);
    assert.equal(alert.baseMinute, 0);
    assert.equal("entryTime" in alert, false);
    assert.equal("patternKind" in alert, false);
  }
  assert.deepEqual(gold.map((alert) => [alert.postSignalRule, alert.symbolH1Signal]), [
    ["cycle-net-keep", "BUY"], ["cycle-net-invert", "SELL"], ["cycle-net-invert", "SELL"],
    ["cycle-net-keep", "BUY"], ["cycle-net-keep", "BUY"], ["cycle-net-keep", "BUY"],
  ]);
  assert.deepEqual(fx.map((alert) => [alert.postSignalRule, alert.symbolH1Signal]), [
    ["cycle-net-keep", "BUY"], ["cycle-net-invert", "SELL"], ["cycle-net-invert", "SELL"],
    ["cycle-net-keep", "BUY"], ["cycle-net-keep", "BUY"], ["cycle-net-keep", "BUY"],
  ]);
});

test("historical days without H1 coverage yield no alerts instead of wrong signals", () => {
  const market = marketForDates("2026-07-06");
  const withoutH1 = Object.fromEntries(Object.entries(market).map(([base, item]) => [base, {
    displayName: item.displayName,
    bars: [],
  }])) as unknown as typeof market;
  const history = reconstructHistoricalDays(withoutH1);
  assert.deepEqual(history, {});
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
  const market = marketForDates("2026-07-03", "2026-07-06");
  const reconstructed = reconstructHistoricalDays(market);
  const state = emptyCloudState();
  const first = mergeHistoricalBackfill(state, reconstructed, "2026-07-06", { includeMissingCurrentDay: true });
  const second = mergeHistoricalBackfill(state, reconstructed, "2026-07-06", { includeMissingCurrentDay: true });
  assert.deepEqual(second, { addedDays: 0, addedAlerts: 0 });
  assert.ok(first.addedAlerts > 0);
});
