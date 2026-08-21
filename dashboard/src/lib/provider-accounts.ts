import "server-only";

import { randomUUID } from "node:crypto";
import { redis } from "@/lib/redis-core";
import { listManagedCTraderAccounts, updateManagedCTraderAccount } from "@/lib/ctrader-accounts";
import {
  assertUniqueProviderLabels,
  cTraderProviderAccountId,
  normalizeAccountLabel,
  normalizeMt5Registration,
  normalizePositivePoints,
  parseCTraderProviderAccountId,
  type Mt5RegistrationInput,
  type ProviderAccountSummary,
  type ProviderEnvironment,
} from "@/lib/provider-account-domain";

const MT5_ACCOUNTS_KEY = "oak:provider-accounts:mt5:v1";
const DEFAULT_ACCOUNT_KEY = "oak:provider-accounts:default:v1";

export type ManagedMt5Account = {
  id: string;
  broker: string;
  environment: ProviderEnvironment;
  login: number;
  label: string;
  enabled: boolean;
  bridgeProfile: string;
  fxSlPoints: number;
  fxTpPoints: number;
  goldSlPoints: number;
  goldTpPoints: number;
  createdAt: number;
  updatedAt: number;
};

function parseMt5Account(raw: unknown): ManagedMt5Account | null {
  try {
    const value = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!value || typeof value !== "object") return null;
    const row = value as Partial<ManagedMt5Account>;
    if (!/^mt5:[A-Za-z0-9_-]{8,80}$/.test(String(row.id || ""))) return null;
    if (row.environment !== "live" && row.environment !== "demo") return null;
    const login = Number(row.login || 0);
    if (!Number.isSafeInteger(login) || login <= 0) return null;
    return {
      id: String(row.id),
      broker: String(row.broker || "MT5").trim().slice(0, 80),
      environment: row.environment,
      login,
      label: String(row.label || login).trim().slice(0, 80),
      enabled: row.enabled === true,
      bridgeProfile: String(row.bridgeProfile || "").trim().slice(0, 120),
      fxSlPoints: normalizePositivePoints(row.fxSlPoints, 500),
      fxTpPoints: normalizePositivePoints(row.fxTpPoints, 10000),
      goldSlPoints: normalizePositivePoints(row.goldSlPoints, 1000),
      goldTpPoints: normalizePositivePoints(row.goldTpPoints, 20000),
      createdAt: Number(row.createdAt || Date.now()),
      updatedAt: Number(row.updatedAt || Date.now()),
    };
  } catch {
    return null;
  }
}

export async function listManagedMt5Accounts(): Promise<ManagedMt5Account[]> {
  const rows = await redis.hgetall<Record<string, unknown>>(MT5_ACCOUNTS_KEY);
  if (!rows) return [];
  return Object.values(rows)
    .map(parseMt5Account)
    .filter((value): value is ManagedMt5Account => Boolean(value))
    .sort((left, right) => Number(right.enabled) - Number(left.enabled) || left.broker.localeCompare(right.broker) || left.login - right.login);
}

export async function getDefaultProviderAccountId(): Promise<string> {
  return String(await redis.get<string>(DEFAULT_ACCOUNT_KEY) || "");
}

export async function listProviderAccounts(): Promise<ProviderAccountSummary[]> {
  const [ctrader, mt5, defaultId] = await Promise.all([
    listManagedCTraderAccounts(),
    listManagedMt5Accounts(),
    getDefaultProviderAccountId(),
  ]);
  const output: ProviderAccountSummary[] = [
    ...ctrader.map((account) => ({
      id: cTraderProviderAccountId(account.accountId),
      provider: "ctrader" as const,
      broker: account.broker,
      environment: account.environment,
      externalAccountId: String(account.accountId),
      traderLogin: account.traderLogin,
      label: account.label,
      enabled: account.enabled,
      isDefault: defaultId === cTraderProviderAccountId(account.accountId),
      connectionMode: "oauth" as const,
      bridgeProfile: null,
      fxSlPoints: account.fxSlPoints,
      fxTpPoints: account.fxTpPoints,
      goldSlPoints: account.goldSlPoints,
      goldTpPoints: account.goldTpPoints,
      updatedAt: account.updatedAt,
    })),
    ...mt5.map((account) => ({
      id: account.id,
      provider: "mt5" as const,
      broker: account.broker,
      environment: account.environment,
      externalAccountId: String(account.login),
      traderLogin: account.login,
      label: account.label,
      enabled: account.enabled,
      isDefault: defaultId === account.id,
      connectionMode: "bridge" as const,
      bridgeProfile: account.bridgeProfile || null,
      fxSlPoints: account.fxSlPoints,
      fxTpPoints: account.fxTpPoints,
      goldSlPoints: account.goldSlPoints,
      goldTpPoints: account.goldTpPoints,
      updatedAt: account.updatedAt,
    })),
  ];
  return output.sort((left, right) => Number(right.isDefault) - Number(left.isDefault) || Number(right.enabled) - Number(left.enabled) || left.provider.localeCompare(right.provider) || left.label.localeCompare(right.label));
}

async function ensureUniqueLabel(label: string, exceptId = ""): Promise<void> {
  assertUniqueProviderLabels(await listProviderAccounts(), label, exceptId);
}

export async function createManagedMt5Account(input: Mt5RegistrationInput): Promise<ManagedMt5Account> {
  const normalized = normalizeMt5Registration(input);
  const accounts = await listManagedMt5Accounts();
  if (accounts.some((item) => item.login === normalized.login && item.broker.toLowerCase() === normalized.broker.toLowerCase() && item.environment === normalized.environment)) {
    throw new Error("MT5 account already registered for this broker/environment");
  }
  await ensureUniqueLabel(normalized.label);
  const now = Date.now();
  const account: ManagedMt5Account = {
    id: `mt5:${randomUUID().replace(/-/g, "")}`,
    ...normalized,
    enabled: false,
    createdAt: now,
    updatedAt: now,
  };
  await redis.hset(MT5_ACCOUNTS_KEY, { [account.id]: JSON.stringify(account) });
  return account;
}

export async function updateManagedMt5Account(id: string, patch: Partial<Pick<ManagedMt5Account, "label" | "enabled" | "bridgeProfile" | "fxSlPoints" | "fxTpPoints" | "goldSlPoints" | "goldTpPoints">>): Promise<ManagedMt5Account> {
  const accounts = await listManagedMt5Accounts();
  const current = accounts.find((item) => item.id === id);
  if (!current) throw new Error(`Unknown MT5 account: ${id}`);
  const label = patch.label === undefined ? current.label : normalizeAccountLabel(patch.label, `${current.broker} ${current.login}`);
  await ensureUniqueLabel(label, id);
  const next: ManagedMt5Account = {
    ...current,
    label,
    enabled: patch.enabled === undefined ? current.enabled : patch.enabled === true,
    bridgeProfile: patch.bridgeProfile === undefined ? current.bridgeProfile : String(patch.bridgeProfile || "").trim().replace(/\s+/g, " ").slice(0, 120),
    fxSlPoints: normalizePositivePoints(patch.fxSlPoints, current.fxSlPoints),
    fxTpPoints: normalizePositivePoints(patch.fxTpPoints, current.fxTpPoints),
    goldSlPoints: normalizePositivePoints(patch.goldSlPoints, current.goldSlPoints),
    goldTpPoints: normalizePositivePoints(patch.goldTpPoints, current.goldTpPoints),
    updatedAt: Date.now(),
  };
  await redis.hset(MT5_ACCOUNTS_KEY, { [id]: JSON.stringify(next) });
  if (!next.enabled && await getDefaultProviderAccountId() === id) await redis.del(DEFAULT_ACCOUNT_KEY);
  return next;
}

export async function updateProviderAccount(id: string, patch: {
  label?: string;
  enabled?: boolean;
  bridgeProfile?: string;
  fxSlPoints?: number;
  fxTpPoints?: number;
  goldSlPoints?: number;
  goldTpPoints?: number;
}): Promise<ProviderAccountSummary> {
  const cTraderAccountId = parseCTraderProviderAccountId(id);
  if (cTraderAccountId !== null) {
    const label = patch.label === undefined ? undefined : normalizeAccountLabel(patch.label, String(cTraderAccountId));
    if (label !== undefined) await ensureUniqueLabel(label, id);
    await updateManagedCTraderAccount(cTraderAccountId, {
      label,
      enabled: patch.enabled,
      fxSlPoints: patch.fxSlPoints,
      fxTpPoints: patch.fxTpPoints,
      goldSlPoints: patch.goldSlPoints,
      goldTpPoints: patch.goldTpPoints,
    });
    if (patch.enabled === false && await getDefaultProviderAccountId() === id) await redis.del(DEFAULT_ACCOUNT_KEY);
  } else if (id.startsWith("mt5:")) {
    await updateManagedMt5Account(id, patch);
  } else {
    throw new Error("Unknown provider account ID");
  }
  const account = (await listProviderAccounts()).find((item) => item.id === id);
  if (!account) throw new Error("Provider account disappeared after update");
  return account;
}

export async function setDefaultProviderAccount(id: string): Promise<ProviderAccountSummary> {
  const account = (await listProviderAccounts()).find((item) => item.id === id);
  if (!account) throw new Error("Unknown provider account");
  if (!account.enabled) throw new Error("Enable an account before making it default");
  await redis.set(DEFAULT_ACCOUNT_KEY, id);
  return { ...account, isDefault: true };
}

export async function clearDefaultProviderAccount(id: string): Promise<void> {
  if (await getDefaultProviderAccountId() === id) await redis.del(DEFAULT_ACCOUNT_KEY);
}

export async function deleteManagedMt5Account(id: string): Promise<boolean> {
  const account = (await listManagedMt5Accounts()).find((item) => item.id === id);
  if (!account) return false;
  await redis.hdel(MT5_ACCOUNTS_KEY, id);
  if (await getDefaultProviderAccountId() === id) await redis.del(DEFAULT_ACCOUNT_KEY);
  return true;
}
