import assert from "node:assert/strict";
import test from "node:test";

import { parseBrokerOffset, resolveBrokerTimestamp } from "../src/lib/broker-time.ts";
import {
  filterActiveSignals,
  filterDisplayableSignals,
  getEntryTimeLabel,
  getSignalTime,
  getTargetHours,
  isPostSpecialMonday,
  isSpecialBrokerDate,
  TARGET_HOURS,
} from "../src/lib/constants.ts";

test("uses only the approved logical slots and signal times", () => {
  assert.deepEqual(TARGET_HOURS, [3, 4, 5, 6, 9, 12, 14, 16]);
  assert.deepEqual(TARGET_HOURS.map((hour) => getSignalTime(hour)), [
    "03:00", "04:45", "05:45", "06:00", "09:00", "12:00", "14:00", "16:00",
  ]);
  assert.equal(getSignalTime(9, "2026-08-06"), "08:00");
  assert.equal(getEntryTimeLabel(6, "2026-08-06"), "06:11");
  assert.equal(getEntryTimeLabel(9, "2026-08-06"), "08:30");
  assert.equal(getEntryTimeLabel(16, "2026-08-11"), "16:11/16:49");
  assert.deepEqual(
    filterActiveSignals([{ hour: 2 }, { hour: 3 }, { hour: 11 }, { hour: 15 }, { hour: 16 }, { hour: 1500 }]),
    [{ hour: 3 }, { hour: 16 }],
  );
});

test("recognizes the remaining paired special dates in 2026", () => {
  const dates = [
    "2026-07-30", "2026-07-31", "2026-08-06", "2026-08-07", "2026-08-27", "2026-08-28",
    "2026-09-03", "2026-09-04", "2026-09-24", "2026-09-25", "2026-10-01", "2026-10-02",
    "2026-10-29", "2026-10-30", "2026-11-26", "2026-11-27", "2026-12-03", "2026-12-04",
    "2026-12-24", "2026-12-25",
  ];
  for (const date of dates) assert.equal(isSpecialBrokerDate(date), true, date);
  assert.equal(isSpecialBrokerDate("2026-08-13"), false);
  assert.equal(isSpecialBrokerDate("2026-12-31"), false);
  assert.equal(isSpecialBrokerDate("2027-01-01"), false);
});

test("suppresses H12, H14 and H16 on special and post-special sessions", () => {
  assert.deepEqual(getTargetHours(4, "2026-08-06"), [3, 4, 5, 6, 9]);
  assert.equal(isPostSpecialMonday("2026-08-10"), true);
  assert.deepEqual(getTargetHours(1, "2026-08-10"), [3, 4, 5, 6, 9]);
  assert.deepEqual(getTargetHours(2, "2026-08-11"), [3, 4, 5, 6, 9, 12, 14, 16]);
  assert.deepEqual(filterDisplayableSignals([
    { date: "2026-08-06", hour: 9 },
    { date: "2026-08-06", hour: 12 },
    { date: "2026-08-11", hour: 12 },
  ]), [
    { date: "2026-08-06", hour: 9 },
    { date: "2026-08-11", hour: 12 },
  ]);
});

test("rejects legacy H3 records after the logical-slot repurpose", () => {
  assert.deepEqual(filterDisplayableSignals([
    { date: "2026-07-25", hour: 3 },
    { date: "2026-07-26", hour: 3, logic_version: 39 },
    { date: "2026-07-27", hour: 3, logic_version: 40 },
    { date: "2026-07-27", hour: 4 },
  ]), [
    { date: "2026-07-27", hour: 3, logic_version: 40 },
    { date: "2026-07-27", hour: 4 },
  ]);
});

test("converts local time only when the record carries a Broker UTC offset", () => {
  assert.equal(parseBrokerOffset(-12), -720);
  assert.equal(parseBrokerOffset("UTC+14:00"), 840);
  assert.equal(parseBrokerOffset(15), null);
  assert.equal(parseBrokerOffset("UTC-13:00"), null);
  assert.equal(resolveBrokerTimestamp({
    date: "2026-08-06",
    brokerTime: "03:11",
  }), null);
  assert.equal(resolveBrokerTimestamp({
    date: "2026-08-06",
    brokerTime: "03:11",
    brokerUtcOffset: "+03:00",
  }), Date.UTC(2026, 7, 6, 0, 11));
  assert.equal(resolveBrokerTimestamp({
    date: "2026-08-06",
    brokerTime: "03:00",
    brokerUtcOffset: 3,
    utcTimestamp: "2026-08-06T00:00:00Z",
  }), Date.UTC(2026, 7, 6, 0, 0));
});
