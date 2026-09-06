export const REDIS_FAILOVER_MARKER_VALUE = "backup-active";

export function shouldUseRedisBackup(localUnavailableUntil: number, sharedMarker: unknown, nowMs = Date.now()): boolean {
  return localUnavailableUntil > nowMs || sharedMarker === REDIS_FAILOVER_MARKER_VALUE;
}

const TRANSIENT_REDIS_ERROR_CODES = new Set([
  "ECONNRESET", "ECONNREFUSED", "ECONNABORTED", "ETIMEDOUT", "ENOTFOUND", "EAI_AGAIN", "EPIPE",
  "EHOSTUNREACH", "EHOSTDOWN", "ENETRESET", "ENETUNREACH",
  "UND_ERR_CONNECT_TIMEOUT", "UND_ERR_HEADERS_TIMEOUT", "UND_ERR_BODY_TIMEOUT", "UND_ERR_SOCKET",
]);

export function isRedisFailoverError(error: unknown): boolean {
  const source = error && typeof error === "object" ? error as Record<string, unknown> : null;
  const cause = source?.cause && typeof source.cause === "object" ? source.cause as Record<string, unknown> : null;
  const status = Number(source?.status ?? source?.statusCode);
  if (Number.isFinite(status) && status > 0) return status === 408 || status === 429 || status >= 500;

  const code = String(source?.code ?? cause?.code ?? "").toUpperCase();
  if (TRANSIENT_REDIS_ERROR_CODES.has(code)) return true;

  const name = String(source?.name ?? "");
  if (/^(TimeoutError|FetchError|NetworkError)$/i.test(name)) return true;

  const message = [source?.message, cause?.message, error instanceof Error ? error.message : error]
    .filter(Boolean)
    .map((value) => String(value))
    .join(" ");
  if (/quota|rate.?limit|too many requests|max(?:imum)? requests|daily request limit|request limit exceeded|\b429\b|\b5\d\d\b/i.test(message)) return true;
  return /fetch failed|failed to fetch|socket hang up|network socket disconnected|connection (?:reset|refused|closed)|timed? out|timeout|temporarily unavailable|service unavailable|bad gateway|gateway timeout|\bdns\b|\benotfound\b|\beai_again\b|\beconn(?:reset|refused|aborted)\b|\bepipe\b|\betimedout\b/i.test(message);
}
