import "server-only";

import { redis } from "./redis-core";

// Local-primary fence: the PC-local controller heartbeats this key while it owns
// Telegram timing and MT5 execution. Cloud execution routes must fail closed while
// the key exists so a re-registered webhook can never produce duplicate orders.
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
  return (await readLocalPrimaryFence()) !== null;
}
