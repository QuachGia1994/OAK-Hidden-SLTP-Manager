import { Redis } from "@upstash/redis";
import { NextResponse } from "next/server";
import { isRedisFailoverError } from "./redis-failover";

const REDIS_URL = process.env.UPSTASH_REDIS_REST_URL || "";
const REDIS_TOKEN = process.env.UPSTASH_REDIS_REST_TOKEN || "";
const BACKUP_REDIS_URL = process.env.UPSTASH_BACKUP_REDIS_REST_URL || "";
const BACKUP_REDIS_TOKEN = process.env.UPSTASH_BACKUP_REDIS_REST_TOKEN || "";
const API_KEY = process.env.DASHBOARD_API_KEY || "";
const FAILOVER_COOLDOWN_MS = Math.max(60_000, Number(process.env.UPSTASH_FAILOVER_COOLDOWN_MS || 600_000));

const primaryRedis = new Redis({ url: REDIS_URL, token: REDIS_TOKEN });
const backupRedis = BACKUP_REDIS_URL && BACKUP_REDIS_TOKEN
  ? new Redis({ url: BACKUP_REDIS_URL, token: BACKUP_REDIS_TOKEN })
  : null;

let primaryUnavailableUntil = 0;

const MUTATING_REDIS_METHODS = new Set([
  "append", "decr", "decrby", "del", "eval", "expire", "expireat", "flushall", "flushdb",
  "hdel", "hincrby", "hincrbyfloat", "hset", "incr", "incrby", "incrbyfloat", "lpop", "lpush",
  "lrem", "lset", "ltrim", "mset", "persist", "pexpire", "pexpireat", "rename", "renamenx", "rpop",
  "rpush", "sadd", "set", "setbit", "setex", "setnx", "srem", "unlink", "zadd", "zincrby", "zrem",
]);

function redisMethod(client: Redis, property: PropertyKey): ((...args: unknown[]) => Promise<unknown>) | null {
  const value = Reflect.get(client, property, client);
  return typeof value === "function" ? value.bind(client) as (...args: unknown[]) => Promise<unknown> : null;
}

async function callBackup(property: PropertyKey, args: unknown[]): Promise<unknown> {
  if (!backupRedis) throw new Error("Upstash backup is not configured");
  const method = redisMethod(backupRedis, property);
  if (!method) throw new Error(`Unsupported Redis method: ${String(property)}`);
  return method(...args);
}

async function callRedis(property: PropertyKey, args: unknown[]): Promise<unknown> {
  const methodName = String(property).toLowerCase();
  const useBackup = Boolean(backupRedis && Date.now() < primaryUnavailableUntil);
  if (useBackup) return callBackup(property, args);

  const primaryMethod = redisMethod(primaryRedis, property);
  if (!primaryMethod) throw new Error(`Unsupported Redis method: ${String(property)}`);
  try {
    const result = await primaryMethod(...args);
    primaryUnavailableUntil = 0;
    if (backupRedis && MUTATING_REDIS_METHODS.has(methodName)) {
      try {
        await callBackup(property, args);
      } catch (error) {
        console.warn("[redis] backup mirror write failed", { method: methodName, error: String(error) });
      }
    }
    return result;
  } catch (error) {
    if (!backupRedis || !isRedisFailoverError(error)) throw error;
    primaryUnavailableUntil = Date.now() + FAILOVER_COOLDOWN_MS;
    console.warn("[redis] primary unavailable; using backup", { method: methodName, cooldownMs: FAILOVER_COOLDOWN_MS });
    return callBackup(property, args);
  }
}

export const redis = new Proxy(primaryRedis, {
  get(target, property, receiver) {
    const value = Reflect.get(target, property, receiver);
    if (typeof value !== "function") return value;
    return (...args: unknown[]) => callRedis(property, args);
  },
}) as Redis;

export async function syncRedisBackup(): Promise<{ scanned: number; copied: number; skipped: number }> {
  if (!backupRedis) throw new Error("Upstash backup is not configured");
  let cursor = 0;
  let scanned = 0;
  let copied = 0;
  let skipped = 0;
  do {
    const [nextCursor, keys] = await primaryRedis.scan(cursor, { count: 100 });
    cursor = Number(nextCursor);
    for (const key of keys) {
      scanned += 1;
      const type = await primaryRedis.type(key);
      const ttlMs = Number(await primaryRedis.pttl(key));
      await backupRedis.del(key);
      if (type === "string") {
        const value = await primaryRedis.get<unknown>(key);
        if (value !== null) await backupRedis.set(key, value);
      } else if (type === "hash") {
        const value = await primaryRedis.hgetall<Record<string, unknown>>(key);
        if (value && Object.keys(value).length) await backupRedis.hset(key, value);
      } else if (type === "list") {
        const value = await primaryRedis.lrange<unknown>(key, 0, -1);
        for (const item of value) await backupRedis.rpush(key, item);
      } else if (type === "set") {
        const value = await primaryRedis.smembers(key);
        for (const item of value) await backupRedis.sadd(key, item);
      } else {
        skipped += 1;
        continue;
      }
      if (ttlMs > 0) await backupRedis.pexpire(key, ttlMs);
      copied += 1;
    }
  } while (cursor !== 0);
  return { scanned, copied, skipped };
}

const RELEASE_OWNED_LOCK_SCRIPT = `
local current = redis.call("GET", KEYS[1])
if current == ARGV[1] then
  return redis.call("DEL", KEYS[1])
end
return 0
`;

const PUSH_TRIMMED_LIST_SCRIPT = `
redis.call("LPUSH", KEYS[1], ARGV[1])
redis.call("LTRIM", KEYS[1], 0, tonumber(ARGV[2]) - 1)
return 1
`;

export async function releaseOwnedRedisLock(key: string, token: string): Promise<void> {
  await redis.eval(RELEASE_OWNED_LOCK_SCRIPT, [key], [token]);
}

export async function pushTrimmedRedisList(key: string, value: string, maxEntries: number): Promise<void> {
  const limit = Math.max(1, Math.trunc(maxEntries));
  await redis.eval(PUSH_TRIMMED_LIST_SCRIPT, [key], [value, String(limit)]);
}

function safeEqual(left: string, right: string): boolean {
  if (left.length !== right.length) return false;
  let diff = 0;
  for (let index = 0; index < left.length; index += 1) {
    diff |= left.charCodeAt(index) ^ right.charCodeAt(index);
  }
  return diff === 0;
}

export function requireAuth(request: Request): NextResponse | null {
  if (!API_KEY) {
    return NextResponse.json({ error: "server auth not configured" }, { status: 503 });
  }
  const supplied = request.headers.get("x-api-key") || "";
  if (!safeEqual(supplied, API_KEY)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  return null;
}

function isSameOriginBrowserRequest(request: Request): boolean {
  const fetchSite = request.headers.get("sec-fetch-site") || "";
  if (fetchSite !== "same-origin") return false;
  if (request.method === "GET") return true;
  const origin = request.headers.get("origin") || "";
  return origin === new URL(request.url).origin;
}

export function requireBrowserOrApiAuth(request: Request): NextResponse | null {
  if (isSameOriginBrowserRequest(request)) return null;
  return requireAuth(request);
}
