import { redis } from "@/lib/redis-core";
import { buildServerRateLimitKeys } from "./server-rate-limit-key";

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

export async function enforceServerRateLimit(
  request: Request,
  policy: ServerRateLimitPolicy,
): Promise<ServerRateLimitExceeded | null> {
  const { minuteKey, dailyKey } = buildServerRateLimitKeys(request, policy);
  const minuteCount = await redis.incr(minuteKey);
  if (minuteCount === 1) await redis.expire(minuteKey, 90);
  if (minuteCount > policy.perMinute) return { scope: "minute", retryAfterSeconds: 60 };

  const dailyCount = await redis.incr(dailyKey);
  if (dailyCount === 1) await redis.expire(dailyKey, 172800);
  if (dailyCount > policy.perDay) return { scope: "day", retryAfterSeconds: 86400 };

  return null;
}
