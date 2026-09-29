import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";

const backfillRoute = readFileSync(new URL("../app/api/h1-scanner/backfill/route.ts", import.meta.url), "utf8");
const scanner = readFileSync(new URL("../../../local-failover/oak-local-h1-scanner.mjs", import.meta.url), "utf8");
const legacyBackfillModule = new URL("./h1-history-backfill.ts", import.meta.url);
const legacyPatternModule = new URL("./h1-local-patterns.ts", import.meta.url);

test("automatic H1 history reconstruction is removed while fixed schedule history remains route-independent", () => {
  assert.equal(existsSync(legacyBackfillModule), false);
  assert.equal(existsSync(legacyPatternModule), false);
  assert.match(backfillRoute, /local-mt5-history-only/);
  assert.doesNotMatch(backfillRoute, /reconstructHistoricalDays|fetchHistoricalBrokerH1|evaluateH1SignalsForTarget/);
});

test("local H1 scanner cannot mutate history from market data while calculation is disabled", () => {
  assert.match(scanner, /calculationDisabled: true/);
  assert.match(scanner, /changedDays: 0/);
  assert.match(scanner, /days: 0/);
  assert.doesNotMatch(scanner, /MAX_BACKFILL_DAYS|snapshotBarsForSource|snapshotH1BarsForSource|MetaTrader5/);
});
