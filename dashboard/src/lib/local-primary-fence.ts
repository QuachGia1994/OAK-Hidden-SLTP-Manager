import "server-only";

import { redis } from "./redis-core";

// Local-only trading is the production default. Cloud broker-mutation routes stay
// fail-closed even if Redis/fence heartbeat is unavailable. The Redis fence is kept
// as rollback/diagnostic evidence but is no longer required for safety.
export const LOCAL_ONLY_TRADING = true;
export const LOCAL_PRIMARY_FENCE_KEY = "oak:telegram:local-primary:active:v1";
export const LOCAL_PRIMARY_FENCE_TTL_SECONDS = 300;

export type LocalPrimaryMt5Heartbeat = {
  providerAccountId: string;
  profile: string;
  login: number;
  server: string;
  at: number;
  localReady: boolean;
  eaVersion: string;
};

export type LocalPrimaryFence = {
  at: number;
  epoch: string;
  accounts: LocalPrimaryMt5Heartbeat[];
};

export async function readLocalPrimaryFence(): Promise<LocalPrimaryFence | null> {
  const raw = await redis.get<unknown>(LOCAL_PRIMARY_FENCE_KEY);
  if (!raw) return null;
  try {
    const parsed = (typeof raw === "string" ? JSON.parse(raw) : raw) as Partial<LocalPrimaryFence>;
    if (typeof parsed.at !== "number" || !Number.isFinite(parsed.at)) return null;
    const accounts = Array.isArray(parsed.accounts)
      ? parsed.accounts.flatMap((row) => {
          const value = row as Partial<LocalPrimaryMt5Heartbeat>;
          const login = Number(value.login);
          const at = Number(value.at);
          if (!Number.isSafeInteger(login) || login <= 0 || !Number.isFinite(at)) return [];
          return [{
            providerAccountId: String(value.providerAccountId || ""),
            profile: String(value.profile || ""),
            login,
            server: String(value.server || ""),
            at,
            localReady: value.localReady !== false,
            eaVersion: String(value.eaVersion || ""),
          }];
        })
      : [];
    return { at: parsed.at, epoch: String(parsed.epoch || ""), accounts };
  } catch {
    // Unparseable fence evidence still means a controller claimed ownership.
    return { at: 0, epoch: "", accounts: [] };
  }
}

export async function writeLocalPrimaryFence(value: LocalPrimaryFence): Promise<void> {
  await redis.set(LOCAL_PRIMARY_FENCE_KEY, JSON.stringify(value), { ex: LOCAL_PRIMARY_FENCE_TTL_SECONDS });
}

export async function isLocalPrimaryActive(): Promise<boolean> {
  if (LOCAL_ONLY_TRADING) return true;
  return (await readLocalPrimaryFence()) !== null;
}
