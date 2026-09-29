import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { H1_FIXED_ENTRY_TIMES } from "./h1-entry-schedule.ts";

const readerSource = readFileSync(new URL("./h1-signals.ts", import.meta.url), "utf8");
const boardSource = readFileSync(new URL("../components/H1SignalBoard.tsx", import.meta.url), "utf8");
const scannerSource = readFileSync(new URL("./h1-cloud-scanner.ts", import.meta.url), "utf8");
const localRouteSource = readFileSync(new URL("../app/api/h1-scanner/local-market/route.ts", import.meta.url), "utf8");

test("H1 reader is a static schedule shell and no longer reads signal state from Redis", () => {
  assert.match(readerSource, /staticSchedulePayload/);
  assert.match(readerSource, /H1_STATIC_HISTORY_CALENDAR_DAYS = 90/);
  assert.match(readerSource, /alerts: \[\]/);
  assert.match(readerSource, /hours: \[\.\.\.H1_SCAN_HOURS\]/);
  assert.match(readerSource, /symbols: \[\.\.\.H1_PUBLIC_SYMBOLS\]/);
  assert.doesNotMatch(readerSource, /readRedisReplicas|parseCloudState|buildPublicFeed|freshestPayload|freshestState/);
});

test("fixed BUY/SELL entry-time source of truth matches owner values", () => {
  assert.deepEqual(H1_FIXED_ENTRY_TIMES, {
    3: { SELL: "07:25", BUY: "07:40" },
    4: { SELL: "08:25", BUY: "10:40" },
    7: { SELL: "11:25", BUY: "13:40" },
    10: { SELL: "15:49", BUY: "16:40" },
    13: { SELL: "18:49", BUY: "19:40" },
    16: { SELL: "20:49", BUY: "21:40" },
  });
});

test("web H1 board renders fixed BUY/SELL rows instead of calculated signal/evidence cells", () => {
  assert.match(boardSource, /H1_FIXED_ENTRY_ROWS/);
  assert.match(boardSource, /fixedH1EntryTime\(side, hour\)/);
  assert.match(boardSource, /<b>\{side\}<\/b>/);
  assert.doesNotMatch(boardSource, /H1EvidencePanel|entryAlertForHour|signalAlertForHour|signalLabel/);
  assert.doesNotMatch(boardSource, /alert\?\.signal|postSignalInverted|patternGroup/);
});

test("scanner rule v102 contains no candle/pattern evaluation exports", () => {
  assert.match(scannerSource, /H1_SIGNAL_RULE_VERSION = 102/);
  assert.doesNotMatch(scannerSource, /evaluateLocalH1Pattern|evaluateLocalH1PatternsForTarget|evaluateH1SignalsForTarget/);
  assert.doesNotMatch(scannerSource, /signalFromDirection|invertSignal|h1BlockSignalPlan|gbpAudH1Signal/);
  assert.doesNotMatch(scannerSource, /h1TpRollMilestonesForBrokerDate/);
  assert.match(localRouteSource, /calculationDisabled: true/);
});

test("web H1 schedule contains every fixed entry time", () => {
  for (const time of [
    "07:25", "07:40", "08:25", "10:40", "11:25", "13:40",
    "15:49", "16:40", "18:49", "19:40", "20:49", "21:40",
  ]) {
    assert.match(JSON.stringify(H1_FIXED_ENTRY_TIMES), new RegExp(time.replace(":", "\\:")));
  }
});
