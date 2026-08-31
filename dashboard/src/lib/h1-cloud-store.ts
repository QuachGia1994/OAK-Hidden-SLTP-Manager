import "server-only";

import { randomUUID } from "node:crypto";
import { readRedisReplicas, redis, releaseOwnedRedisLock } from "./redis-core";
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

type H1StateCandidate = {
  state: H1CloudState;
  source: "cloud" | "public-seed";
};

function stateProgress(state: H1CloudState): [string, number, number] {
  const latestDate = Object.keys(state.days).sort().at(-1) || "";
  if (!latestDate) return ["", -1, 0];
  const alerts = Object.values(state.days[latestDate]?.symbols || {}).flatMap((symbol) => symbol?.alerts || []);
  const latestHour = alerts.reduce((max, alert) => Math.max(max, alert.slotHour), -1);
  return [latestDate, latestHour, alerts.length];
}

function compareStateProgress(left: H1CloudState, right: H1CloudState): number {
  const a = stateProgress(left);
  const b = stateProgress(right);
  if (a[0] !== b[0]) return a[0].localeCompare(b[0]);
  if (a[1] !== b[1]) return a[1] - b[1];
  return a[2] - b[2];
}

function parseCloudCandidate(raw: unknown): H1StateCandidate | null {
  if (!raw) return null;
  try {
    return { state: parseCloudState(raw), source: "cloud" };
  } catch {
    return null;
  }
}

function parsePublicCandidate(raw: unknown): H1StateCandidate | null {
  try {
    const state = parsePublicFeedCloudState(raw);
    return state ? { state, source: "public-seed" } : null;
  } catch {
    return null;
  }
}

async function loadFreshestH1Candidate(): Promise<H1StateCandidate | null> {
  const [stateReplicas, feedReplicas] = await Promise.all([
    readRedisReplicas<unknown>(H1_CLOUD_STATE_KEY),
    readRedisReplicas<unknown>(H1_PUBLIC_LATEST_KEY),
  ]);
  const candidates = [
    parseCloudCandidate(stateReplicas.primary),
    parseCloudCandidate(stateReplicas.backup),
    parsePublicCandidate(feedReplicas.primary),
    parsePublicCandidate(feedReplicas.backup),
  ].filter((candidate): candidate is H1StateCandidate => Boolean(candidate));

  return candidates.reduce<H1StateCandidate | null>((best, candidate) => {
    if (!best) return candidate;
    const progress = compareStateProgress(candidate.state, best.state);
    if (progress > 0) return candidate;
    if (progress === 0 && candidate.source === "cloud" && best.source !== "cloud") return candidate;
    return best;
  }, null);
}

export async function loadH1CloudState(
  brokerDate: string,
  brokerHour: number,
): Promise<{ state: H1CloudState; source: "cloud" | "public-seed" }> {
  const freshest = await loadFreshestH1Candidate();
  if (freshest) return freshest;
  return { state: seedCloudStateFromPublic(null, brokerDate, brokerHour), source: "public-seed" };
}

export async function loadH1CloudHistoryState(): Promise<{ state: H1CloudState; source: "cloud" | "public-seed" | "empty" }> {
  const freshest = await loadFreshestH1Candidate();
  return freshest || { state: emptyCloudState(), source: "empty" };
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
