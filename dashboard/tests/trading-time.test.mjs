import assert from "node:assert/strict";
import test from "node:test";

import { BROKER_CLOCK_MAX_AGE_MS, getBrokerDateParts } from "../src/lib/trading-time.ts";

const validState = {
  date: "2026-08-06",
  broker_utc_offset: 3,
  broker_time: "2026-08-06T03:00:00",
  broker_observed_at_utc: "2026-08-06T00:00:00+00:00",
};

test("advances a fresh, consistent Broker clock from its UTC observation", () => {
  assert.deepEqual(getBrokerDateParts(validState, new Date("2026-08-06T00:02:30Z")), {
    currentHour: 3,
    currentMinute: 2,
    dayOfWeek: 4,
    todayStr: "2026-08-06",
  });
});

test("fails closed for missing, stale, future or inconsistent observations", () => {
  assert.equal(getBrokerDateParts(null, new Date("2026-08-06T00:00:00Z")), null);
  assert.equal(getBrokerDateParts(
    validState,
    new Date(Date.parse("2026-08-06T00:00:00Z") + BROKER_CLOCK_MAX_AGE_MS + 1),
  ), null);
  assert.equal(getBrokerDateParts(validState, new Date("2026-08-05T23:59:29Z")), null);
  assert.equal(getBrokerDateParts({ ...validState, broker_utc_offset: 2 }, new Date("2026-08-06T00:01:00Z")), null);
  assert.equal(getBrokerDateParts({ ...validState, broker_utc_offset: -13 }, new Date("2026-08-06T00:01:00Z")), null);
  assert.equal(getBrokerDateParts({ ...validState, broker_observed_at_utc: "2026-08-06T00:00:00" }, new Date("2026-08-06T00:01:00Z")), null);
  assert.equal(getBrokerDateParts({ ...validState, date: "2026-08-05" }, new Date("2026-08-06T00:01:00Z")), null);
});

test("derives the Broker calendar date across a UTC day boundary", () => {
  const state = {
    date: "2026-08-07",
    broker_utc_offset: 3,
    broker_time: "2026-08-07T00:59:00",
    broker_observed_at_utc: "2026-08-06T21:59:00Z",
  };
  assert.deepEqual(getBrokerDateParts(state, new Date("2026-08-06T22:01:00Z")), {
    currentHour: 1,
    currentMinute: 1,
    dayOfWeek: 5,
    todayStr: "2026-08-07",
  });
});
