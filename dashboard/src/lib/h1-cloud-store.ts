import "server-only";

import { randomUUID } from "node:crypto";
import { redis, releaseOwnedRedisLock } from "./redis-core";
import {
  H1_CLOUD_LOCK_KEY,
  H1_CLOUD_PROFILE,
  H1_CLOUD_STATE_KEY,
  H1_PUBLIC_LATEST_KEY,
  buildPublicFeed,
  emptyCloudState,
  parseCloudState,
  parsePublicFeedCloudState,
  seedCloudStateFromPublic,
  trimCloudState,
  type H1CloudState,
} from "./h1-cloud-scanner";

const PUBLIC_PROFILE_KEY = `robot-sltp:public:h1-signals:${H1_CLOUD_PROFILE}`;
export const H1_CLOUD_LOCK_SECONDS = 90;

export async function loadH1CloudState(
  brokerDate: string,
  brokerHour: number,
): Promise<{ state: H1CloudState; source: "cloud" | "public-seed" }> {
  const existing = await redis.get<unknown>(H1_CLOUD_STATE_KEY);
  if (existing) return { state: parseCloudState(existing), source: "cloud" };
  const publicFeed = await redis.get<unknown>(H1_PUBLIC_LATEST_KEY);
  return { state: seedCloudStateFromPublic(publicFeed, brokerDate, brokerHour), source: "public-seed" };
}

export async function loadH1CloudHistoryState(): Promise<{ state: H1CloudState; source: "cloud" | "public-seed" | "empty" }> {
  const existing = await redis.get<unknown>(H1_CLOUD_STATE_KEY);
  if (existing) return { state: parseCloudState(existing), source: "cloud" };
  const publicFeed = await redis.get<unknown>(H1_PUBLIC_LATEST_KEY);
  const seeded = parsePublicFeedCloudState(publicFeed);
  return seeded ? { state: seeded, source: "public-seed" } : { state: emptyCloudState(), source: "empty" };
}

export async function saveH1CloudState(state: H1CloudState): Promise<void> {
  trimCloudState(state);
  parseCloudState(state);
  await redis.set(H1_CLOUD_STATE_KEY, state);
}

export async function publishH1CloudState(state: H1CloudState): Promise<void> {
  parseCloudState(state);
  const feed = buildPublicFeed(state);
  await redis.mset({
    [PUBLIC_PROFILE_KEY]: feed,
    [H1_PUBLIC_LATEST_KEY]: feed,
  });
}

export async function acquireH1CloudLock(): Promise<string | null> {
  const token = randomUUID();
  const result = await redis.set(H1_CLOUD_LOCK_KEY, token, { nx: true, ex: H1_CLOUD_LOCK_SECONDS });
  return result === "OK" ? token : null;
}

export async function releaseH1CloudLock(token: string): Promise<void> {
  try {
    await releaseOwnedRedisLock(H1_CLOUD_LOCK_KEY, token);
  } catch {
    // Lock TTL is the final safety net; release failure must not mask the scanner/backfill result.
  }
}
