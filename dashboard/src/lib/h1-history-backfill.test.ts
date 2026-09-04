import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const localRoute = readFileSync(new URL("../app/api/h1-scanner/local-market/route.ts", import.meta.url), "utf8");
const legacyBackfillRoute = readFileSync(new URL("../app/api/h1-scanner/backfill/route.ts", import.meta.url), "utf8");
const publisher = readFileSync(new URL("../../../local-failover/oak-local-h1-scanner.mjs", import.meta.url), "utf8");
const reader = readFileSync(new URL("../../../local-failover/mt5-h1-market-reader.py", import.meta.url), "utf8");

test("rule v76 history is rebuilt from local ICMarkets M15 snapshots, not legacy cTrader H1 reconstruction", () => {
  assert.match(legacyBackfillRoute, /local-mt5-history-only/);
  assert.doesNotMatch(legacyBackfillRoute, /reconstructHistoricalDays|fetchHistoricalBrokerH1/);
  assert.match(localRoute, /evaluateLocalH1PatternsForTarget/);
  assert.match(localRoute, /saveH1CloudState/);
  assert.match(localRoute, /publishH1CloudState/);
});

test("local history publisher is bounded to 90 calendar days and carries every previous broker-day signal base", () => {
  assert.match(publisher, /MAX_BACKFILL_DAYS = 90/);
  assert.match(publisher, /previousAvailableDate/);
  assert.match(publisher, /PREVIOUS_DAY_BASE_SOURCES\.has\(source\)/);
  assert.match(publisher, /snapshotBarsForSource/);
  assert.match(localRoute, /MAX_BARS_PER_SOURCE = 220/);
  assert.match(publisher, /dateSnapshots/);
  assert.match(publisher, /brokerHour: currentDay \? payload\.brokerHour : 23/);
  assert.match(publisher, /for \(const snapshot of snapshots\)/);
  assert.match(publisher, /await postSnapshot\(config, snapshot, fetchImpl, \{ retryBusy: true \}\)/);
  assert.match(publisher, /body\?\.skipped === "already-running"/);
});

test("local M15 reader fetches enough retained bars while excluding the still-open candle", () => {
  assert.match(reader, /MAX_DAYS = 120/);
  assert.match(reader, /days \* 96 \+ 192/);
  assert.match(reader, /for row in rates\[:-1\]:/);
  assert.match(reader, /TIMEFRAME_M15/);
});
