import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const localRoute = readFileSync(new URL("../app/api/h1-scanner/local-market/route.ts", import.meta.url), "utf8");
const legacyBackfillRoute = readFileSync(new URL("../app/api/h1-scanner/backfill/route.ts", import.meta.url), "utf8");
const publisher = readFileSync(new URL("../../../local-failover/oak-local-h1-scanner.mjs", import.meta.url), "utf8");
const reader = readFileSync(new URL("../../../local-failover/mt5-h1-market-reader.py", import.meta.url), "utf8");

test("rule v94 history is rebuilt from local ICMarkets XAUUSD entry + GBPUSD M15 base snapshots, not legacy cTrader reconstruction", () => {
  assert.match(legacyBackfillRoute, /local-mt5-history-only/);
  assert.doesNotMatch(legacyBackfillRoute, /reconstructHistoricalDays|fetchHistoricalBrokerH1/);
  assert.match(localRoute, /evaluateLocalH1PatternsForTarget/);
  assert.match(localRoute, /saveH1CloudState/);
  assert.match(localRoute, /publishH1CloudState/);
});

test("local history publisher is bounded to 90 calendar days and carries only XAUUSD/GBPUSD v94 market sources", () => {
  assert.match(publisher, /MAX_BACKFILL_DAYS = 90/);
  assert.match(publisher, /snapshotBarsForSource/);
  assert.match(publisher, /snapshotH1BarsForSource/);
  assert.match(publisher, /h1Bars/);
  assert.doesNotMatch(publisher, /previousAvailableXauDate|snapshotBarsWithH3Context/);
  assert.match(publisher, /SOURCE_KEYS = \["XAUUSD", "GBPUSD"\]/);
  assert.match(localRoute, /MAX_BARS_PER_SOURCE = 220/);
  assert.match(publisher, /dateSnapshots/);
  assert.match(publisher, /brokerHour: currentDay \? payload\.brokerHour : 23/);
  assert.match(publisher, /for \(const snapshot of snapshots\)/);
  assert.match(publisher, /await postSnapshot\(config, snapshot, fetchImpl, \{ retryBusy: true \}\)/);
  assert.match(publisher, /body\?\.skipped === "already-running"/);
});

test("local reader fetches retained M15 + H1 bars while excluding both still-open candles", () => {
  assert.match(reader, /MAX_DAYS = 120/);
  assert.match(reader, /days \* 96 \+ 192/);
  assert.match(reader, /days \* 24 \+ 72/);
  assert.match(reader, /for row in m15_rates\[:-1\]:/);
  assert.match(reader, /for row in h1_rates\[:-1\]:/);
  assert.match(reader, /TIMEFRAME_M15/);
  assert.match(reader, /TIMEFRAME_H1/);
  assert.match(reader, /"version": 2/);
});
