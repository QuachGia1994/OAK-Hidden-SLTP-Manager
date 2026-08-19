import assert from "node:assert/strict";
import test from "node:test";
import { buildServerRateLimitKeys } from "./server-rate-limit-key.ts";

const policy = { namespace: "sltp:factcheck-media", perMinute: 3, perDay: 80 };
const now = Date.UTC(2026, 7, 19, 3, 30, 0);

function requestFor(ip: string): Request {
  return new Request("https://www.oakgatekeeper.uk/api/factcheck/media", {
    headers: { "x-forwarded-for": ip },
  });
}

test("daily rate-limit bucket is isolated per client", () => {
  const first = buildServerRateLimitKeys(requestFor("203.0.113.10"), policy, now);
  const second = buildServerRateLimitKeys(requestFor("203.0.113.11"), policy, now);
  assert.notEqual(first.dailyKey, second.dailyKey);
  assert.match(first.dailyKey, /:daily:203\.0\.113\.10:2026-08-19$/);
  assert.match(second.dailyKey, /:daily:203\.0\.113\.11:2026-08-19$/);
});

test("same client shares the same daily bucket but minute bucket rotates", () => {
  const first = buildServerRateLimitKeys(requestFor("203.0.113.10"), policy, now);
  const later = buildServerRateLimitKeys(requestFor("203.0.113.10"), policy, now + 61_000);
  assert.equal(first.dailyKey, later.dailyKey);
  assert.notEqual(first.minuteKey, later.minuteKey);
});
