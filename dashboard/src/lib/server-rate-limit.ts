import { redis } from "@/lib/redis-core";

export interface ServerRateLimitPolicy {
  namespace: string;
  perMinute: number;
  perDay: number;
}

export interface ServerRateLimitExceeded {
  scope: "minute" | "day";
  retryAfterSeconds: number;
}

export function readPositiveLimit(value: string | undefined, fallback: number): number {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

function clientKey(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for") || request.headers.get("x-real-ip") || "unknown";
  return forwarded.split(",")[0].trim().replace(/[^a-zA-Z0-9:._-]/g, "_").slice(0, 96);
}

export async function enforceServerRateLimit(
  request: Request,
  policy: ServerRateLimitPolicy,
): Promise<ServerRateLimitExceeded | null> {
  const namespace = policy.namespace.replace(/[^a-zA-Z0-9:_-]/g, "_");
  const minuteBucket = Math.floor(Date.now() / 60000);
  const minuteKey = `${namespace}:rate:${clientKey(request)}:${minuteBucket}`;
  const minuteCount = await redis.incr(minuteKey);
  if (minuteCount === 1) await redis.expire(minuteKey, 90);
  if (minuteCount > policy.perMinute) return { scope: "minute", retryAfterSeconds: 60 };

  const day = new Date().toISOString().slice(0, 10);
  const dailyKey = `${namespace}:daily:${day}`;
  const dailyCount = await redis.incr(dailyKey);
  if (dailyCount === 1) await redis.expire(dailyKey, 172800);
  if (dailyCount > policy.perDay) return { scope: "day", retryAfterSeconds: 86400 };

  return null;
}
