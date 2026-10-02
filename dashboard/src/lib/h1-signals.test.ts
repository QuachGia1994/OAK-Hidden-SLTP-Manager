import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { H1_FIXED_ENTRY_TIMES, H1_WEEKDAY_PATTERNS } from "./h1-entry-schedule.ts";

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
    3: { SELL: "07:25", BUY: "07:35" },
    4: { SELL: "08:25", BUY: "08:35" },
    7: { SELL: "12:49", BUY: "13:35" },
    11: { SELL: "15:49", BUY: "16:35" },
    14: { SELL: "18:49", BUY: "19:35" },
    16: { SELL: "20:49", BUY: "21:35" },
  });
});

test("weekday C/N pattern source of truth matches owner sheet", () => {
  const flatten = (mode: keyof typeof H1_WEEKDAY_PATTERNS) => H1_WEEKDAY_PATTERNS[mode].map((row) => [row.weekday, row.marks.join("")]);
  assert.deepEqual(flatten("NORMAL"), [[4, "CCCNCN"], [5, "CNNCNC"], [1, "NNCCNC"], [2, "CNNNCN"], [3, "NCCCNN"]]);
  assert.deepEqual(flatten("SW"), [[4, "CCNCNC"], [5, "NNCCNC"], [1, "NNNNCN"], [2, "NCCCNC"], [3, "CNNNCC"]]);
});

test("web H1 board renders weekday C/N pattern rows with fixed BUY/SELL times in the header", () => {
  assert.match(boardSource, /H1_FIXED_ENTRY_ROWS/);
  assert.match(boardSource, /fixedH1EntryTime\(side, hour\)/);
  assert.match(boardSource, /H1_WEEKDAY_PATTERNS\[mode\]/);
  assert.match(boardSource, /className="oak-h1-cn-mark"/);
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
    "07:25", "07:35", "08:25", "08:35", "12:49", "13:35",
    "15:49", "16:35", "18:49", "19:35", "20:49", "21:35",
  ]) {
    assert.match(JSON.stringify(H1_FIXED_ENTRY_TIMES), new RegExp(time.replace(":", "\\:")));
  }
});
