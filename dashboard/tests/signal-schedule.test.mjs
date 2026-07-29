import assert from "node:assert/strict";
import fs from "node:fs";
import test from "node:test";

import {
  brokerTimeToLocal,
  isVerifiedBrokerClockMetadata,
  parseBrokerOffset,
  resolveBrokerTimestamp,
  verifiedBrokerTimeToLocal,
} from "../src/lib/broker-time.ts";
import {
  ACTIVE_SIGNAL_LOGIC_VERSION,
  filterActiveSignals,
  filterDisplayableSignals,
  getDayRules,
  getEntryTimeLabel,
  getSignalTime,
  getTargetHours,
  isPostSpecialMonday,
  isSpecialBrokerDate,
  TARGET_HOURS,
} from "../src/lib/constants.ts";
import { DISPLAYED_SIGNAL_PAIRS, isEffectivelyDeactivated } from "../src/lib/signal-display.ts";

test("uses only the approved logical slots and signal times", () => {
  assert.deepEqual(TARGET_HOURS, [3, 7, 9, 12, 14, 16]);
  assert.deepEqual(TARGET_HOURS.map((hour) => getSignalTime(hour)), [
    "03:00", "07:00", "09:00", "12:00", "14:00", "16:00",
  ]);
  assert.equal(getSignalTime(5), "--:--");
  assert.equal(getEntryTimeLabel(3), "03:49 / 04:25");
  assert.equal(getSignalTime(9, "2026-08-06"), "09:00");
  assert.equal(getEntryTimeLabel(7, "2026-08-06"), "07:49 / 08:25");
  assert.equal(getEntryTimeLabel(9, "2026-08-06"), "09:49 / 10:25");
  assert.equal(getEntryTimeLabel(14, "2026-08-06"), "14:49 / 15:25");
  assert.equal(getEntryTimeLabel(16, "2026-08-11"), "16:49 / 17:25");
  assert.deepEqual(
    filterActiveSignals([{ hour: 2 }, { hour: 3 }, { hour: 5 }, { hour: 11 }, { hour: 15 }, { hour: 16 }, { hour: 1500 }]),
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

test("includes H12, H14 and H16 on special and post-special sessions", () => {
  assert.deepEqual(getTargetHours(4, "2026-08-06"), [3, 7, 9, 12, 14, 16]);
  assert.equal(isPostSpecialMonday("2026-08-10"), true);
  assert.deepEqual(getTargetHours(1, "2026-08-10"), [3, 7, 9, 12, 14, 16]);
  assert.deepEqual(getTargetHours(2, "2026-08-11"), [3, 7, 9, 12, 14, 16]);
  assert.deepEqual(filterDisplayableSignals([
    { date: "2026-08-06", hour: 5, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-08-06", hour: 9, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-08-06", hour: 12, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "SELL", pair_dirs: { XAUUSD: "SELL" } },
    { date: "2026-08-11", hour: 12, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
  ]), [
    { date: "2026-08-06", hour: 9, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-08-06", hour: 12, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "SELL", pair_dirs: { XAUUSD: "SELL" } },
    { date: "2026-08-11", hour: 12, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
  ]);
});

test("rejects every active record before the GBP H1 and XAUUSD M15 contract", () => {
  assert.deepEqual(filterDisplayableSignals([
    { date: "2026-07-25", hour: 3, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-07-26", hour: 3, logic_version: 48, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-07-27", hour: 4, logic_version: 48, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-07-27", hour: 6, logic_version: "49", signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-07-27", hour: "9", logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-02-31", hour: 9, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-07-27", hour: 9, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "SELL", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-07-27", hour: 12, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION + 1, signal: "SELL", pair_dirs: { XAUUSD: "SELL" } },
    { date: "2026-07-27", hour: 5, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { XAUUSD: "BUY" } },
    { date: "2026-07-27", hour: 14, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION, signal: "BUY", pair_dirs: { GBPUSD: "BUY" } },
  ]), [
    { date: "2026-07-27", hour: 12, logic_version: ACTIVE_SIGNAL_LOGIC_VERSION + 1, signal: "SELL", pair_dirs: { XAUUSD: "SELL" } },
  ]);
});

test("converts local time only with verified, consistent Broker clock metadata", () => {
  assert.equal(brokerTimeToLocal("03:00", 3), "07:00");
  assert.equal(brokerTimeToLocal("03:49", 3), "07:49");
  assert.equal(parseBrokerOffset(-12), -720);
  assert.equal(parseBrokerOffset("UTC+14:00"), 840);
  assert.equal(parseBrokerOffset(15), null);
  assert.equal(parseBrokerOffset("UTC-13:00"), null);

  const verifiedUtcMetadata = {
    date: "2026-08-06",
    signalTime: "03:00",
    signalAtUtc: "2026-08-06T03:00:00Z",
    brokerUtcOffset: 0,
    brokerClockVerified: true,
  };
  assert.equal(isVerifiedBrokerClockMetadata(verifiedUtcMetadata), true);
  assert.equal(isVerifiedBrokerClockMetadata({
    ...verifiedUtcMetadata,
    brokerClockVerified: false,
  }), false);

  assert.equal(verifiedBrokerTimeToLocal({
    date: "2026-08-06",
    signalTime: "03:00",
    signalAtUtc: "2026-08-06T00:00:00Z",
    brokerUtcOffset: 3,
    brokerClockVerified: true,
  }, "03:00"), "07:00");
  assert.equal(verifiedBrokerTimeToLocal({
    date: "2026-08-06",
    signalTime: "03:00",
    signalAtUtc: "2026-08-06T03:00:00Z",
    brokerUtcOffset: 3,
    brokerClockVerified: true,
  }, "03:00"), null);
  assert.equal(isVerifiedBrokerClockMetadata({
    ...verifiedUtcMetadata,
    brokerUtcOffset: null,
  }), false);
  assert.equal(isVerifiedBrokerClockMetadata({
    ...verifiedUtcMetadata,
    signalAtUtc: "2026-08-06T03:01:00Z",
  }), false);
  assert.equal(isVerifiedBrokerClockMetadata({
    ...verifiedUtcMetadata,
    signalAtUtc: "2026-08-06T03:00:00",
  }), false);

  assert.equal(resolveBrokerTimestamp({
    ...verifiedUtcMetadata,
    brokerTime: "03:11",
  }), Date.UTC(2026, 7, 6, 3, 11));
  assert.equal(resolveBrokerTimestamp({
    ...verifiedUtcMetadata,
    brokerTime: "03:11",
    brokerClockVerified: undefined,
  }), null);
  assert.equal(resolveBrokerTimestamp({
    date: "2026-08-06",
    brokerTime: "03:00",
    brokerUtcOffset: 3,
    signalTime: "03:00",
    signalAtUtc: "2026-08-06T00:00:00Z",
    brokerClockVerified: true,
  }), Date.UTC(2026, 7, 6, 0, 0));
});

test("derives deactivated card state for safety slots and Thursday H3 placeholders", () => {
  assert.equal(isEffectivelyDeactivated({ date: "2026-08-05", hour: 4 }), true);
  assert.equal(isEffectivelyDeactivated({ date: "2026-08-06", hour: 3 }), true);
  assert.equal(isEffectivelyDeactivated({ date: "2026-08-07", hour: 3 }), false);
  assert.equal(isEffectivelyDeactivated({
    date: "2026-08-07",
    hour: 9,
    deactivated: true,
  }), true);
});

test("renders canonical signal pairs", () => {
  assert.deepEqual(DISPLAYED_SIGNAL_PAIRS, ["XAUUSD", "GBPUSD", "GBPAUD"]);
});

test("does not re-filter already validated history after VIP masking", () => {
  const source = fs.readFileSync(
    new URL("../src/components/HistoryList.tsx", import.meta.url),
    "utf8",
  );
  assert.equal(source.includes("isDisplayableSignal"), false);
});

test("shows the v55 M15 multi-pair rules", () => {
  const rules = getDayRules("EN", 2);
  assert.equal(rules.some((rule) => /M30|priority|compares H6/i.test(rule)), false);
  assert.equal(rules.some((rule) => rule.includes("evaluates XAUUSD, GBPUSD, and GBPAUD independently")), true);
  assert.equal(rules.some((rule) => rule.includes("SW → reverse Base")), true);
  assert.equal(rules.some((rule) => rule.includes("(H+1):25")), true);
});
