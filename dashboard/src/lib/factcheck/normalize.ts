/** Deterministic claim normalization for display and optional exact-match cache keys. */
export function normalizeClaim(text: string): string {
  return text
    .normalize("NFC")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 12000);
}

export function truncateClaim(text: string, max = 120): string {
  const clean = normalizeClaim(text);
  if (clean.length <= max) return clean;
  return `${clean.slice(0, Math.max(0, max - 1)).trimEnd()}…`;
}
