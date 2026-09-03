import "server-only";

import { randomUUID } from "node:crypto";
import { redis } from "@/lib/redis-core";
import { listManagedCTraderAccounts, updateManagedCTraderAccount } from "@/lib/ctrader-accounts";
import { getMt5BridgeHeartbeat } from "@/lib/mt5-bridge";
import { createMt5AutoBindRecord, mt5AutoBindExactKey, mt5AutoBindLoginKey, normalizeMt5Server } from "@/lib/mt5-auto-bind-domain";
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
  bridgeServer: string;
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
      bridgeServer: String(row.bridgeServer || "").trim().replace(/\s+/g, " ").slice(0, 120),
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

function brokerNameFromLocalHeartbeat(profile: string, server: string): string {
  const joined = `${profile} ${server}`;
  if (/icmarkets/i.test(joined)) return "IC Markets";
  if (/vantage/i.test(joined)) return "Vantage";
  if (/neotech|fxce/i.test(joined)) return "FXCE";
  return "MT5";
}

export async function syncManagedMt5AccountsFromLocalHeartbeats(rows: Array<{
  providerAccountId: string;
  profile: string;
  login: number;
  server: string;
  enabled?: boolean;
}>): Promise<{ created: number; updated: number }> {
  const accounts = await listManagedMt5Accounts();
  let created = 0;
  let updated = 0;
  for (const row of rows) {
    const profile = String(row.profile || "").trim();
    const server = String(row.server || "").trim();
    const login = Number(row.login || 0);
    if (!profile || !server || !Number.isSafeInteger(login) || login <= 0) continue;
    const existing = accounts.find((account) =>
      account.id === row.providerAccountId
      || account.bridgeProfile.trim().toLowerCase() === profile.toLowerCase()
      || (account.login === login && normalizeMt5Server(account.bridgeServer) === normalizeMt5Server(server)),
    );
    const now = Date.now();
    if (existing) {
      const enabled = row.enabled !== false;
      const changed = existing.login !== login
        || existing.bridgeProfile !== profile
        || normalizeMt5Server(existing.bridgeServer) !== normalizeMt5Server(server)
        || existing.enabled !== enabled;
      if (changed) {
        const next: ManagedMt5Account = {
          ...existing,
          login,
          bridgeProfile: profile,
          bridgeServer: server,
          enabled,
          updatedAt: now,
        };
        await redis.hset(MT5_ACCOUNTS_KEY, { [existing.id]: JSON.stringify(next) });
        await syncMt5AutoBind(existing, next);
        Object.assign(existing, next);
        updated += 1;
      }
      continue;
    }

    const id = /^mt5:[A-Za-z0-9_-]{8,80}$/.test(row.providerAccountId)
      ? row.providerAccountId
      : `mt5:${randomUUID().replace(/-/g, "")}`;
    const account: ManagedMt5Account = {
      id,
      broker: brokerNameFromLocalHeartbeat(profile, server),
      environment: /demo/i.test(server) ? "demo" : "live",
      login,
      label: profile,
      enabled: row.enabled !== false,
      bridgeProfile: profile,
      bridgeServer: server,
      fxSlPoints: 500,
      fxTpPoints: 10000,
      goldSlPoints: 1000,
      goldTpPoints: 20000,
      createdAt: now,
      updatedAt: now,
    };
    await redis.hset(MT5_ACCOUNTS_KEY, { [id]: JSON.stringify(account) });
    await syncMt5AutoBind(null, account);
    accounts.push(account);
    created += 1;
  }
  return { created, updated };
}

async function syncMt5LoginAutoBind(login: number): Promise<void> {
  const enabled = (await listManagedMt5Accounts()).filter((account) => account.enabled && account.bridgeProfile && account.login === login);
  if (enabled.length === 1 && !enabled[0].bridgeServer) {
    await redis.set(mt5AutoBindLoginKey(login), JSON.stringify(createMt5AutoBindRecord(enabled[0])));
    return;
  }
  await redis.del(mt5AutoBindLoginKey(login));
}

async function deleteMt5ExactAutoBind(account: ManagedMt5Account): Promise<void> {
  if (!account.bridgeServer) return;
  await redis.del(mt5AutoBindExactKey(account.login, account.bridgeServer));
}

async function writeMt5ExactAutoBind(account: ManagedMt5Account): Promise<void> {
  if (!account.enabled || !account.bridgeProfile || !account.bridgeServer) return;
  await redis.set(mt5AutoBindExactKey(account.login, account.bridgeServer), JSON.stringify(createMt5AutoBindRecord(account)));
}

async function syncMt5AutoBind(previous: ManagedMt5Account | null, next: ManagedMt5Account | null): Promise<void> {
  if (previous) await deleteMt5ExactAutoBind(previous);
  if (next) await writeMt5ExactAutoBind(next);
  const logins = new Set<number>([previous?.login, next?.login].filter((value): value is number => Boolean(value)));
  for (const login of logins) await syncMt5LoginAutoBind(login);
}

export async function reconcileManagedMt5AutoBind(): Promise<{ total: number; mapped: number; serverFilled: number; unresolved: number; conflicts: string[] }> {
  const accounts = (await listManagedMt5Accounts()).filter((account) => account.enabled && account.bridgeProfile);
  let mapped = 0;
  let serverFilled = 0;
  let unresolved = 0;
  const conflicts: string[] = [];
  for (const account of accounts) {
    const heartbeat = await getMt5BridgeHeartbeat(account.bridgeProfile);
    if (!heartbeat || heartbeat.login !== account.login || !String(heartbeat.server || "").trim()) {
      unresolved += 1;
      continue;
    }
    if (account.bridgeServer && normalizeMt5Server(account.bridgeServer) !== normalizeMt5Server(heartbeat.server)) {
      conflicts.push(account.id);
      continue;
    }
    let next = account;
    if (!account.bridgeServer) {
      next = { ...account, bridgeServer: String(heartbeat.server).trim(), updatedAt: Date.now() };
      await redis.hset(MT5_ACCOUNTS_KEY, { [account.id]: JSON.stringify(next) });
      serverFilled += 1;
    }
    await syncMt5AutoBind(account.bridgeServer ? null : account, next);
    mapped += 1;
  }
  return { total: accounts.length, mapped, serverFilled, unresolved, conflicts };
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
      bridgeServer: null,
      fxSlPoints: account.fxSlPoints,
      fxTpPoints: account.fxTpPoints,
      goldSlPoints: account.goldSlPoints,
      goldTpPoints: account.goldTpPoints,
      manager: account.manager,
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
      bridgeServer: account.bridgeServer || null,
      fxSlPoints: account.fxSlPoints,
      fxTpPoints: account.fxTpPoints,
      goldSlPoints: account.goldSlPoints,
      goldTpPoints: account.goldTpPoints,
      manager: null,
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
  await syncMt5AutoBind(null, account);
  return account;
}

export async function updateManagedMt5Account(id: string, patch: Partial<Pick<ManagedMt5Account, "label" | "enabled" | "bridgeProfile" | "bridgeServer" | "fxSlPoints" | "fxTpPoints" | "goldSlPoints" | "goldTpPoints">>): Promise<ManagedMt5Account> {
  const accounts = await listManagedMt5Accounts();
  const current = accounts.find((item) => item.id === id);
  if (!current) throw new Error(`Unknown MT5 account: ${id}`);
  const label = patch.label === undefined ? current.label : normalizeAccountLabel(patch.label, `${current.broker} ${current.login}`);
  await ensureUniqueLabel(label, id);
  const bridgeProfile = patch.bridgeProfile === undefined ? current.bridgeProfile : String(patch.bridgeProfile || "").trim().replace(/\s+/g, " ").slice(0, 120);
  const bridgeServer = patch.bridgeServer === undefined ? current.bridgeServer : String(patch.bridgeServer || "").trim().replace(/\s+/g, " ").slice(0, 120);
  const enabled = patch.enabled === undefined ? current.enabled : patch.enabled === true;
  if (enabled && !bridgeProfile) throw new Error("MT5 bridge profile is required before enabling the account");
  if (enabled && accounts.some((item) => item.id !== id && item.enabled && item.bridgeProfile.trim().toLowerCase() === bridgeProfile.toLowerCase())) {
    throw new Error(`MT5 bridge profile is already assigned: ${bridgeProfile}`);
  }
  if (enabled && bridgeServer && accounts.some((item) => item.id !== id && item.enabled && item.login === current.login && item.bridgeServer && normalizeMt5Server(item.bridgeServer) === normalizeMt5Server(bridgeServer))) {
    throw new Error("Another enabled MT5 account already uses this login/server identity");
  }
  const next: ManagedMt5Account = {
    ...current,
    label,
    enabled,
    bridgeProfile,
    bridgeServer,
    fxSlPoints: normalizePositivePoints(patch.fxSlPoints, current.fxSlPoints),
    fxTpPoints: normalizePositivePoints(patch.fxTpPoints, current.fxTpPoints),
    goldSlPoints: normalizePositivePoints(patch.goldSlPoints, current.goldSlPoints),
    goldTpPoints: normalizePositivePoints(patch.goldTpPoints, current.goldTpPoints),
    updatedAt: Date.now(),
  };
  await redis.hset(MT5_ACCOUNTS_KEY, { [id]: JSON.stringify(next) });
  await syncMt5AutoBind(current, next);
  if (!next.enabled && await getDefaultProviderAccountId() === id) await redis.del(DEFAULT_ACCOUNT_KEY);
  return next;
}

export async function updateProviderAccount(id: string, patch: {
  label?: string;
  enabled?: boolean;
  bridgeProfile?: string;
  bridgeServer?: string;
  fxSlPoints?: number;
  fxTpPoints?: number;
  goldSlPoints?: number;
  goldTpPoints?: number;
  manager?: import("@/lib/ctrader-manager-domain").CTraderManagerSettings;
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
      manager: patch.manager,
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
  await syncMt5AutoBind(account, null);
  if (await getDefaultProviderAccountId() === id) await redis.del(DEFAULT_ACCOUNT_KEY);
  return true;
}
