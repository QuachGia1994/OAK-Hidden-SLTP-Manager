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

let lastStorageFailureLogAt = 0;

export async function enforceServerRateLimit(
  request: Request,
  policy: ServerRateLimitPolicy,
): Promise<ServerRateLimitExceeded | null> {
  try {
    const { minuteKey, dailyKey } = buildServerRateLimitKeys(request, policy);
    const minuteCount = await redis.incr(minuteKey);
    if (minuteCount === 1) await redis.expire(minuteKey, 90);
    if (minuteCount > policy.perMinute) return { scope: "minute", retryAfterSeconds: 60 };

    const dailyCount = await redis.incr(dailyKey);
    if (dailyCount === 1) await redis.expire(dailyKey, 172800);
    if (dailyCount > policy.perDay) return { scope: "day", retryAfterSeconds: 86400 };

    return null;
  } catch (error) {
    // Storage outage (e.g. Upstash request quota exhausted): fail OPEN so the
    // whole service is not taken down by the rate limiter. Log at most once per
    // minute per process to avoid flooding server logs on every request.
    if (Date.now() - lastStorageFailureLogAt > 60_000) {
      lastStorageFailureLogAt = Date.now();
      console.error("[RATE LIMIT DEGRADED] storage unavailable", error instanceof Error ? error.message : String(error));
    }
    return null;
  }
}
