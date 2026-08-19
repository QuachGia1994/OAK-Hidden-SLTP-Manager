export interface RateLimitKeyPolicy {
  namespace: string;
}

function clientKey(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for") || request.headers.get("x-real-ip") || "unknown";
  return forwarded.split(",")[0].trim().replace(/[^a-zA-Z0-9:._-]/g, "_").slice(0, 96);
}

export function buildServerRateLimitKeys(
  request: Request,
  policy: RateLimitKeyPolicy,
  now = Date.now(),
): { minuteKey: string; dailyKey: string } {
  const namespace = policy.namespace.replace(/[^a-zA-Z0-9:_-]/g, "_");
  const client = clientKey(request);
  const minuteBucket = Math.floor(now / 60000);
  const day = new Date(now).toISOString().slice(0, 10);
  return {
    minuteKey: `${namespace}:rate:${client}:${minuteBucket}`,
    dailyKey: `${namespace}:daily:${client}:${day}`,
  };
}
