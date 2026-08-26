import { createHash } from "node:crypto";

export const MT5_AUTO_BIND_VERSION = 1 as const;
const AUTO_BIND_PREFIX = "oak:mt5:bridge:auto-bind:v1:";

export type Mt5AutoBindRecord = {
  version: typeof MT5_AUTO_BIND_VERSION;
  providerAccountId: string;
  bridgeProfile: string;
  login: number;
  serverHash: string;
};

function positiveLogin(value: number): number {
  const login = Number(value);
  if (!Number.isSafeInteger(login) || login <= 0) throw new Error("MT5 login must be a positive integer");
  return login;
}

export function normalizeMt5Server(value: string): string {
  return String(value || "").trim().replace(/\s+/g, " ").toLowerCase();
}

export function mt5ServerHash(server: string): string {
  const normalized = normalizeMt5Server(server);
  if (!normalized) return "";
  return createHash("sha256").update(normalized, "utf8").digest("hex").slice(0, 40);
}

export function mt5AutoBindExactKey(login: number, server: string): string {
  const hash = mt5ServerHash(server);
  if (!hash) throw new Error("MT5 server is required for exact auto-bind");
  return `${AUTO_BIND_PREFIX}exact:${positiveLogin(login)}:${hash}`;
}

export function mt5AutoBindLoginKey(login: number): string {
  return `${AUTO_BIND_PREFIX}login:${positiveLogin(login)}`;
}

export function createMt5AutoBindRecord(account: {
  id: string;
  login: number;
  bridgeProfile: string;
  bridgeServer?: string;
}): Mt5AutoBindRecord {
  const providerAccountId = String(account.id || "").trim();
  const bridgeProfile = String(account.bridgeProfile || "").trim();
  if (!/^mt5:[A-Za-z0-9_-]{8,80}$/.test(providerAccountId)) throw new Error("Invalid MT5 provider account id");
  if (!bridgeProfile) throw new Error("MT5 bridge profile is required");
  return {
    version: MT5_AUTO_BIND_VERSION,
    providerAccountId,
    bridgeProfile,
    login: positiveLogin(account.login),
    serverHash: mt5ServerHash(account.bridgeServer || ""),
  };
}
