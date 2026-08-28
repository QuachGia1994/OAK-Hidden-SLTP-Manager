import test from "node:test";
import assert from "node:assert/strict";
import { currentBoundary, nextBoundary, scannerOutcomeNeedsRetry, scannerScheduleMode } from "./src/index.js";

test("timekeeper boundaries align to exact UTC top of hour", () => {
  const now = Date.UTC(2026, 7, 21, 9, 52, 17, 321);
  assert.equal(currentBoundary(now), Date.UTC(2026, 7, 21, 9, 0, 0, 0));
  assert.equal(nextBoundary(now), Date.UTC(2026, 7, 21, 10, 0, 0, 0));
});

test("scanner retry policy retries concurrency and unfinalized H1 outcomes", () => {
  assert.equal(scannerOutcomeNeedsRetry(200, { ok: true, skipped: "already-running" }), true);
  assert.equal(scannerOutcomeNeedsRetry(200, { ok: true, skipped: "awaiting-closed-h1" }), true);
  assert.equal(scannerOutcomeNeedsRetry(200, { ok: true, skipped: "disabled" }), true);
  assert.equal(scannerOutcomeNeedsRetry(502, { ok: false }), true);
  assert.equal(scannerOutcomeNeedsRetry(200, { ok: true, sent: 0 }), false);
  assert.equal(scannerOutcomeNeedsRetry(200, { ok: true, skipped: "broker-weekend" }), false);
});

test("scanner phases make every minute tick also heal a missed H1 alarm", () => {
  assert.equal(scannerScheduleMode("* * * * *"), "telegram-watchdog");
  assert.equal(scannerScheduleMode("1 * * * *"), "follow-up");
  assert.equal(scannerScheduleMode("15 * * * *"), "follow-up");
  assert.equal(scannerScheduleMode("30 * * * *"), "follow-up");
  assert.equal(scannerScheduleMode("10 * * * *"), "watchdog");
  assert.equal(scannerScheduleMode("50 * * * *"), "watchdog");
});
