import assert from "node:assert/strict";
import test from "node:test";

import { isRedisFailoverError } from "./redis-failover.ts";

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
