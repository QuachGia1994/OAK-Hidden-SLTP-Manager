import "server-only";

import { redis } from "@/lib/redis-core";

const ACCOUNTS_KEY = "oak:ctrader:managed-accounts:v1";

export type CTraderManagedAccount = {
  accountId: number;
  traderLogin: number | null;
  broker: string;
  environment: "live" | "demo";
  label: string;
  enabled: boolean;
  fxSlPoints: number;
  fxTpPoints: number;
  goldSlPoints: number;
  goldTpPoints: number;
  discoveredAt: number;
  updatedAt: number;
};

export type CTraderGrantedAccount = {
  accountId: number;
  traderLogin: number | null;
  broker: string;
  environment: "live" | "demo";
};

function defaults(source: CTraderGrantedAccount, enabled: boolean, now: number): CTraderManagedAccount {
  return {
    ...source,
    label: source.traderLogin ? String(source.traderLogin) : `${source.broker} ${source.accountId}`,
    enabled,
    fxSlPoints: 500,
    fxTpPoints: 10000,
    goldSlPoints: 1000,
    goldTpPoints: 20000,
    discoveredAt: now,
    updatedAt: now,
  };
}

function parseAccount(raw: unknown): CTraderManagedAccount | null {
  try {
    const value = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!value || typeof value !== "object") return null;
    const row = value as Partial<CTraderManagedAccount>;
    if (!Number.isInteger(row.accountId) || Number(row.accountId) <= 0) return null;
    if (row.environment !== "live" && row.environment !== "demo") return null;
    return {
      accountId: Number(row.accountId),
      traderLogin: Number.isInteger(row.traderLogin) && Number(row.traderLogin) > 0 ? Number(row.traderLogin) : null,
      broker: String(row.broker || "cTrader"),
      environment: row.environment,
      label: String(row.label || row.traderLogin || row.accountId),
      enabled: row.enabled === true,
      fxSlPoints: Math.max(0, Number(row.fxSlPoints || 500)),
      fxTpPoints: Math.max(0, Number(row.fxTpPoints || 10000)),
      goldSlPoints: Math.max(0, Number(row.goldSlPoints || 1000)),
      goldTpPoints: Math.max(0, Number(row.goldTpPoints || 20000)),
      discoveredAt: Number(row.discoveredAt || Date.now()),
      updatedAt: Number(row.updatedAt || Date.now()),
    };
  } catch {
    return null;
  }
}

export async function listManagedCTraderAccounts(): Promise<CTraderManagedAccount[]> {
  const rows = await redis.hgetall<Record<string, unknown>>(ACCOUNTS_KEY);
  if (!rows) return [];
  return Object.values(rows)
    .map(parseAccount)
    .filter((value): value is CTraderManagedAccount => Boolean(value))
    .sort((left, right) => Number(right.enabled) - Number(left.enabled) || left.broker.localeCompare(right.broker) || left.accountId - right.accountId);
}

export async function syncManagedCTraderAccounts(granted: CTraderGrantedAccount[], now = Date.now()): Promise<CTraderManagedAccount[]> {
  const existing = new Map((await listManagedCTraderAccounts()).map((item) => [item.accountId, item]));
  const legacyAccountId = Number.parseInt(process.env.OAK_CTRADER_ACCOUNT_ID || "", 10) || 0;
  const updates: Record<string, string> = {};
  for (const source of granted) {
    if (!Number.isInteger(source.accountId) || source.accountId <= 0) continue;
    const previous = existing.get(source.accountId);
    const next = previous
      ? { ...previous, traderLogin: source.traderLogin, broker: source.broker, environment: source.environment, updatedAt: now }
      : defaults(source, source.accountId === legacyAccountId, now);
    updates[String(source.accountId)] = JSON.stringify(next);
  }
  if (Object.keys(updates).length) await redis.hset(ACCOUNTS_KEY, updates);
  return listManagedCTraderAccounts();
}

export async function updateManagedCTraderAccount(accountId: number, patch: Partial<Pick<CTraderManagedAccount, "label" | "enabled" | "fxSlPoints" | "fxTpPoints" | "goldSlPoints" | "goldTpPoints">>): Promise<CTraderManagedAccount> {
  const accounts = await listManagedCTraderAccounts();
  const current = accounts.find((item) => item.accountId === accountId);
  if (!current) throw new Error(`Unknown cTrader account: ${accountId}`);
  const next: CTraderManagedAccount = {
    ...current,
    label: patch.label === undefined ? current.label : String(patch.label).trim().slice(0, 80) || String(current.traderLogin || current.accountId),
    enabled: patch.enabled === undefined ? current.enabled : patch.enabled === true,
    fxSlPoints: patch.fxSlPoints === undefined ? current.fxSlPoints : Math.max(0, Number(patch.fxSlPoints)),
    fxTpPoints: patch.fxTpPoints === undefined ? current.fxTpPoints : Math.max(0, Number(patch.fxTpPoints)),
    goldSlPoints: patch.goldSlPoints === undefined ? current.goldSlPoints : Math.max(0, Number(patch.goldSlPoints)),
    goldTpPoints: patch.goldTpPoints === undefined ? current.goldTpPoints : Math.max(0, Number(patch.goldTpPoints)),
    updatedAt: Date.now(),
  };
  for (const value of [next.fxSlPoints, next.fxTpPoints, next.goldSlPoints, next.goldTpPoints]) {
    if (!Number.isFinite(value) || value <= 0) throw new Error("SL/TP points must be positive finite numbers");
  }
  const normalizedLabel = next.label.trim().toLowerCase();
  if (accounts.some((item) => item.accountId !== accountId && item.label.trim().toLowerCase() === normalizedLabel)) {
    throw new Error(`Duplicate account label: ${next.label}`);
  }
  await redis.hset(ACCOUNTS_KEY, { [String(accountId)]: JSON.stringify(next) });
  return next;
}

export function resolveEnabledAccountTargets(accounts: CTraderManagedAccount[], alias = ""): CTraderManagedAccount[] {
  const enabled = accounts.filter((item) => item.enabled);
  const needle = String(alias || "").trim().toLowerCase();
  if (!needle) return enabled;
  if (["vantage", "vantagedemo", "darwinex", "th5ers"].includes(needle)) {
    return enabled.length === 1 ? enabled : [];
  }
  return enabled.filter((item) =>
    item.label.trim().toLowerCase() === needle
    || String(item.traderLogin || "") === needle
    || item.broker.trim().toLowerCase() === needle,
  );
}

export function defaultProtectionPoints(account: CTraderManagedAccount, symbol: string): { sl: number; tp: number } {
  const gold = /XAU|GOLD/i.test(symbol);
  return gold
    ? { sl: account.goldSlPoints, tp: account.goldTpPoints }
    : { sl: account.fxSlPoints, tp: account.fxTpPoints };
}
