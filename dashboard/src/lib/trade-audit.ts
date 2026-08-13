import { redis, KEYS } from "./redis";

export interface TradeAuditPayloads {
  overview: unknown | null;
  positions: unknown | null;
  checkpoints: unknown | null;
  ledger: unknown | null;
  performance: unknown | null;
  risk: unknown | null;
  audit: unknown | null;
  equity: unknown | null;
}

export async function getTradeAuditOverview(): Promise<unknown | null> {
  try {
    return (await redis.get(KEYS.auditOverview)) ?? null;
  } catch {
    return null;
  }
}

export async function getTradeAuditPositions(): Promise<unknown | null> {
  try {
    return (await redis.get(KEYS.auditPositions)) ?? null;
  } catch {
    return null;
  }
}

export async function getTradeAuditCheckpoints(): Promise<unknown | null> {
  try {
    return (await redis.get(KEYS.auditCheckpoints)) ?? null;
  } catch {
    return null;
  }
}

export async function getTradeAuditLedger(): Promise<unknown | null> {
  try {
    return (await redis.get(KEYS.auditLedger)) ?? null;
  } catch {
    return null;
  }
}

export async function getTradeAuditPerformance(): Promise<unknown | null> {
  try {
    return (await redis.get(KEYS.auditPerformance)) ?? null;
  } catch {
    return null;
  }
}

export async function getTradeAuditRisk(): Promise<unknown | null> {
  try {
    return (await redis.get(KEYS.auditRisk)) ?? null;
  } catch {
    return null;
  }
}

export async function getTradeAuditInfo(): Promise<unknown | null> {
  try {
    return (await redis.get(KEYS.auditInfo)) ?? null;
  } catch {
    return null;
  }
}

export async function getTradeAuditEquity(): Promise<unknown | null> {
  try {
    return (await redis.get(KEYS.auditEquity)) ?? null;
  } catch {
    return null;
  }
}

export async function getTradeAuditAll(): Promise<TradeAuditPayloads> {
  const [overview, positions, checkpoints, ledger, performance, risk, audit, equity] =
    await Promise.all([
      getTradeAuditOverview(),
      getTradeAuditPositions(),
      getTradeAuditCheckpoints(),
      getTradeAuditLedger(),
      getTradeAuditPerformance(),
      getTradeAuditRisk(),
      getTradeAuditInfo(),
      getTradeAuditEquity(),
    ]);
  return { overview, positions, checkpoints, ledger, performance, risk, audit, equity };
}
