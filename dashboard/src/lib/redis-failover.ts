export function isRedisFailoverError(error: unknown): boolean {
  const status = Number((error as { status?: unknown; statusCode?: unknown } | null)?.status
    ?? (error as { statusCode?: unknown } | null)?.statusCode);
  if (status === 429 || status >= 500) return true;
  const message = error instanceof Error ? error.message : String(error || "");
  return /quota|rate.?limit|too many requests|max(?:imum)? requests|daily request limit|request limit exceeded|429|5\d\d/i.test(message);
}
