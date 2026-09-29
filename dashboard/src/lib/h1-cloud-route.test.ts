import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const localRoute = readFileSync(new URL("../app/api/h1-scanner/local-market/route.ts", import.meta.url), "utf8");
const runRoute = readFileSync(new URL("../app/api/h1-scanner/run/route.ts", import.meta.url), "utf8");
const backfillRoute = readFileSync(new URL("../app/api/h1-scanner/backfill/route.ts", import.meta.url), "utf8");
const workflow = readFileSync(new URL("../../../.github/workflows/h1-cloud-scanner.yml", import.meta.url), "utf8");
const publisher = readFileSync(new URL("../../../local-failover/oak-local-h1-scanner.mjs", import.meta.url), "utf8");

test("local H1 endpoint validates provenance but performs no signal calculation", () => {
  assert.match(localRoute, /invalid local H1 snapshot version\/profile/);
  assert.match(localRoute, /local H1 snapshot must come from ICMarkets MT5/);
  assert.match(localRoute, /calculationDisabled: true/);
  assert.match(localRoute, /matched: 0/);
  assert.match(localRoute, /updated: 0/);
  assert.match(localRoute, /tpMilestones: \[\]/);
  assert.doesNotMatch(localRoute, /evaluateLocalH1PatternsForTarget|evaluateH1SignalsForTarget|h1TpRollMilestonesForBrokerDate/);
  assert.doesNotMatch(localRoute, /saveH1CloudState|publishH1CloudState|acquireH1CloudLock/);
});

test("cloud scanner and history routes are no-op placeholders", () => {
  assert.match(runRoute, /local-mt5-push-owned/);
  assert.match(backfillRoute, /local-mt5-history-only/);
  assert.doesNotMatch(runRoute, /evaluateLocalH1PatternsForTarget|evaluateH1SignalsForTarget/);
  assert.doesNotMatch(backfillRoute, /reconstructHistoricalDays|evaluateH1SignalsForTarget/);
});

test("local scanner publisher is calculation-disabled and does not read MT5 candles", () => {
  assert.match(publisher, /H1_SIGNAL_RULE_VERSION = 102/);
  assert.match(publisher, /H1_CALCULATION_DISABLED = true/);
  assert.match(publisher, /calculationDisabled: true/);
  assert.match(publisher, /tpMilestones: \[\]/);
  assert.doesNotMatch(publisher, /MetaTrader5|mt5-h1-market-reader|readIcMarketsM15|bars|h1Bars|fetch\(/);
});

test("H1 workflow no longer schedules or runs automatic scanner/backfill", () => {
  assert.match(workflow, /workflow_dispatch/);
  assert.match(workflow, /H1 signal calculation is intentionally disabled/);
  assert.doesNotMatch(workflow, /schedule:/);
  assert.doesNotMatch(workflow, /api\/h1-scanner\/run|api\/h1-scanner\/backfill/);
});
