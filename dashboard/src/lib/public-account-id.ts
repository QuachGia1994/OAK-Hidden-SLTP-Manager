/** Pure helpers — safe to import from Node tests without Next.js. */

export function isPublicAccountId(value: string | null | undefined): value is string {
  if (!value || typeof value !== "string") return false;
  return /^[a-f0-9]{8,64}$/i.test(value);
}

export function auditKey(baseKey: string, accountId?: string | null): string {
  if (accountId && isPublicAccountId(accountId)) {
    return `${baseKey}:${accountId.toLowerCase()}`;
  }
  return baseKey;
}
