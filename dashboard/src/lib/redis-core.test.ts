import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

import { REDIS_FAILOVER_MARKER_VALUE, isRedisFailoverError, shouldUseRedisBackup } from "./redis-failover.ts";

const redisCoreSource = readFileSync(new URL("./redis-core.ts", import.meta.url), "utf8");

test("Redis failover recognizes quota, rate-limit and upstream outage errors", () => {
  assert.equal(isRedisFailoverError({ status: 429 }), true);
  assert.equal(isRedisFailoverError({ statusCode: 503 }), true);
  assert.equal(isRedisFailoverError(new Error("ERR max requests limit exceeded")), true);
  assert.equal(isRedisFailoverError(new Error("daily request limit exceeded")), true);
});

test("Redis failover does not mask auth or application errors", () => {
  assert.equal(isRedisFailoverError({ status: 401 }), false);
  assert.equal(isRedisFailoverError({ status: 403 }), false);
  assert.equal(isRedisFailoverError(new Error("WRONGTYPE operation against a key")), false);
});

test("shared backup authority survives a fresh serverless process", () => {
  const now = Date.UTC(2026, 7, 31, 3, 5, 0);
  assert.equal(shouldUseRedisBackup(0, REDIS_FAILOVER_MARKER_VALUE, now), true);
  assert.equal(shouldUseRedisBackup(now + 60_000, null, now), true);
  assert.equal(shouldUseRedisBackup(0, null, now), false);
});

test("Redis core persists shared failover authority and blocks stale primary overwrite", () => {
  assert.match(redisCoreSource, /backupRedis\.set\(SHARED_FAILOVER_KEY, REDIS_FAILOVER_MARKER_VALUE\)/);
  assert.match(redisCoreSource, /shouldUseRedisBackup\(primaryUnavailableUntil, marker\)/);
  assert.match(redisCoreSource, /Upstash backup is the active failover authority; primary-to-backup sync is blocked/);
});
