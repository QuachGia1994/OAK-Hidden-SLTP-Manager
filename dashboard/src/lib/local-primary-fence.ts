import "server-only";

import { redis } from "./redis-core";

// Local-only trading is the production default. Cloud broker-mutation routes stay
// fail-closed even if Redis/fence heartbeat is unavailable. The Redis fence is kept
// as rollback/diagnostic evidence but is no longer required for safety.
export const LOCAL_ONLY_TRADING = true;
export const LOCAL_PRIMARY_FENCE_KEY = "oak:telegram:local-primary:active:v1";
export const LOCAL_PRIMARY_FENCE_TTL_SECONDS = 300;

export type LocalPrimaryFence = {
  at: number;
  epoch: string;
};

export async function readLocalPrimaryFence(): Promise<LocalPrimaryFence | null> {
  const raw = await redis.get<string>(LOCAL_PRIMARY_FENCE_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<LocalPrimaryFence>;
    if (typeof parsed.at !== "number" || !Number.isFinite(parsed.at)) return null;
    return { at: parsed.at, epoch: String(parsed.epoch || "") };
  } catch {
    // Unparseable fence evidence still means a controller claimed ownership.
    return { at: 0, epoch: "" };
  }
}

export async function isLocalPrimaryActive(): Promise<boolean> {
  if (LOCAL_ONLY_TRADING) return true;
  return (await readLocalPrimaryFence()) !== null;
}
