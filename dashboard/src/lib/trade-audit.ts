import { redis, KEYS, auditKey, isPublicAccountId } from "./redis";

export interface TradeAuditPayloads {
  overview: unknown | null;
  positions: unknown | null;
  checkpoints: unknown | null;
  ledger: unknown | null;
  performance: unknown | null;
  risk: unknown | null;
  audit: unknown | null;
  equity: unknown | null;
  live: unknown | null;
  public_account_id?: string | null;
}

export interface PublicAccountMeta {
  public_account_id: string;
  alias: string;
}

async function getSection(baseKey: string, accountId?: string | null): Promise<unknown | null> {
  try {
    const key = auditKey(baseKey, accountId);
    const val = await redis.get(key);
    if (val != null) return val;
    // Legacy single-slot fallback only when no account requested.
    if (!accountId) return (await redis.get(baseKey)) ?? null;
    return null;
  } catch {
    return null;
  }
}

export async function listPublicAccounts(): Promise<PublicAccountMeta[]> {
  try {
    const registry = (await redis.get(KEYS.auditAccounts)) as PublicAccountMeta[] | null;
    if (!Array.isArray(registry)) return [];
    return registry.filter(
      (e) => e && isPublicAccountId(e.public_account_id) && typeof e.alias === "string",
    );
  } catch {
    return [];
  }
}

export async function getTradeAuditAll(accountId?: string | null): Promise<TradeAuditPayloads> {
  const account = accountId && isPublicAccountId(accountId) ? accountId.toLowerCase() : null;
  const [overview, positions, checkpoints, ledger, performance, risk, audit, equity, live] =
    await Promise.all([
      getSection(KEYS.auditOverview, account),
      getSection(KEYS.auditPositions, account),
      getSection(KEYS.auditCheckpoints, account),
      getSection(KEYS.auditLedger, account),
      getSection(KEYS.auditPerformance, account),
      getSection(KEYS.auditRisk, account),
      getSection(KEYS.auditInfo, account),
      getSection(KEYS.auditEquity, account),
      getSection(KEYS.auditLive, account),
    ]);
  return {
    overview,
    positions,
    checkpoints,
    ledger,
    performance,
    risk,
    audit,
    equity,
    live,
    public_account_id: account,
  };
}

export async function getTradeAuditOverview(): Promise<unknown | null> {
  return getSection(KEYS.auditOverview, null);
}
export async function getTradeAuditPositions(): Promise<unknown | null> {
  return getSection(KEYS.auditPositions, null);
}
export async function getTradeAuditCheckpoints(): Promise<unknown | null> {
  return getSection(KEYS.auditCheckpoints, null);
}
export async function getTradeAuditLedger(): Promise<unknown | null> {
  return getSection(KEYS.auditLedger, null);
}
export async function getTradeAuditPerformance(): Promise<unknown | null> {
  return getSection(KEYS.auditPerformance, null);
}
export async function getTradeAuditRisk(): Promise<unknown | null> {
  return getSection(KEYS.auditRisk, null);
}
export async function getTradeAuditInfo(): Promise<unknown | null> {
  return getSection(KEYS.auditInfo, null);
}
export async function getTradeAuditEquity(): Promise<unknown | null> {
  return getSection(KEYS.auditEquity, null);
}
