import "server-only";

import { randomUUID } from "node:crypto";
import { brokerWallParts } from "./ctrader-json";
import { readRedisReplicas, redis, releaseOwnedRedisLock } from "./redis-core";
import {
  H1_CLOUD_LOCK_KEY,
  H1_CLOUD_PROFILE,
  H1_CLOUD_STATE_KEY,
  H1_LEGACY_CLOUD_STATE_KEYS,
  H1_PUBLIC_LATEST_KEY,
  buildPublicFeed,
  clearLegacyScheduledSignalAtSlot,
  cycleDecisionFor,
  emptyCloudState,
  ensureSymbolDay,
  h1TargetBaseFromSymbol,
  mergeH1CloudStateHistory,
  parseCloudState,
  parsePublicFeedCloudState,
  scheduledSignalSlotForBrokerHour,
  scheduledSignalSlotForVietnamWall,
  seedCloudStateFromPublic,
  trimCloudState,
  vietnamAppointmentWallParts,
  type H1CloudState,
  type H1Signal,
} from "./h1-cloud-scanner";

const PUBLIC_PROFILE_KEY = `robot-sltp:public:h1-signals:${H1_CLOUD_PROFILE}`;
export const H1_CLOUD_LOCK_SECONDS = 90;

type H1StateCandidate = {
  state: H1CloudState;
  source: "cloud" | "public-seed";
};

function stateProgress(state: H1CloudState): [string, number, number, number] {
  const dateKeys = Object.keys(state.days).sort();
  const latestDate = dateKeys.at(-1) || "";
  if (!latestDate) return ["", -1, 0, 0];
  const alerts = Object.values(state.days[latestDate]?.symbols || {}).flatMap((symbol) => symbol?.alerts || []);
  const latestHour = alerts.reduce((max, alert) => Math.max(max, alert.slotHour), -1);
  return [latestDate, latestHour, alerts.length, dateKeys.length];
}

function compareStateProgress(left: H1CloudState, right: H1CloudState): number {
  const a = stateProgress(left);
  const b = stateProgress(right);
  if (a[0] !== b[0]) return a[0].localeCompare(b[0]);
  if (a[1] !== b[1]) return a[1] - b[1];
  if (a[2] !== b[2]) return a[2] - b[2];
  return a[3] - b[3];
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

function freshestCandidate(candidates: Array<H1StateCandidate | null>): H1StateCandidate | null {
  return candidates.filter((candidate): candidate is H1StateCandidate => Boolean(candidate)).reduce<H1StateCandidate | null>((best, candidate) => {
    if (!best) return candidate;
    const progress = compareStateProgress(candidate.state, best.state);
    if (progress > 0) return candidate;
    if (progress === 0 && candidate.source === "cloud" && best.source !== "cloud") return candidate;
    return best;
  }, null);
}

async function loadCloudKeyCandidate(key: string): Promise<H1StateCandidate | null> {
  const [authoritative, replicas] = await Promise.all([
    redis.get<unknown>(key),
    readRedisReplicas<unknown>(key),
  ]);
  return freshestCandidate([
    parseCloudCandidate(authoritative),
    parseCloudCandidate(replicas.primary),
    parseCloudCandidate(replicas.backup),
  ]);
}

async function loadCurrentPublicCandidate(): Promise<H1StateCandidate | null> {
  const [authoritative, replicas] = await Promise.all([
    redis.get<unknown>(H1_PUBLIC_LATEST_KEY),
    readRedisReplicas<unknown>(H1_PUBLIC_LATEST_KEY),
  ]);
  return freshestCandidate([
    parsePublicCandidate(authoritative),
    parsePublicCandidate(replicas.primary),
    parsePublicCandidate(replicas.backup),
  ]);
}

async function loadLegacyHistoryState(): Promise<H1CloudState | null> {
  const candidates = await Promise.all(H1_LEGACY_CLOUD_STATE_KEYS.map((key) => loadCloudKeyCandidate(key)));
  let merged: H1CloudState | null = null;
  for (const candidate of [...candidates].reverse()) {
    if (!candidate) continue;
    merged = merged ? mergeH1CloudStateHistory(merged, candidate.state) : candidate.state;
  }
  return merged;
}

async function loadFreshestH1Candidate(): Promise<H1StateCandidate | null> {
  // Once the schema-stable state exists it is authoritative. Legacy rule-key
  // reads are migration-only and disappear from the hot path after first save.
  const stable = await loadCloudKeyCandidate(H1_CLOUD_STATE_KEY);
  if (stable) return stable;

  const [legacy, currentFeed] = await Promise.all([
    loadLegacyHistoryState(),
    loadCurrentPublicCandidate(),
  ]);
  if (!legacy && !currentFeed) return null;

  let state = legacy ?? emptyCloudState();
  if (currentFeed) state = mergeH1CloudStateHistory(state, currentFeed.state);
  return { state, source: "public-seed" };
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

export async function writeTelegramScheduledSignal(args: {
  symbol: string;
  side: H1Signal;
  dueAt: number;
}): Promise<{ brokerDate: string; slotHour: number; base: string; side: H1Signal } | null> {
  const base = h1TargetBaseFromSymbol(args.symbol);
  if (!base || !Number.isFinite(args.dueAt) || args.dueAt <= 0) return null;
  const vietnamWall = vietnamAppointmentWallParts(args.dueAt);
  const slotHour = scheduledSignalSlotForVietnamWall(base, vietnamWall.dateKey, vietnamWall.hour, vietnamWall.minute);
  if (slotHour === null) return null;
  const legacyBrokerWall = brokerWallParts(args.dueAt);
  const legacySlotHour = scheduledSignalSlotForBrokerHour(base, legacyBrokerWall.dateKey, legacyBrokerWall.hour);

  const lockToken = await acquireH1CloudLock();
  if (!lockToken) throw new Error("H1 table is busy; scheduled signal write must retry");
  try {
    const { state } = await loadH1CloudState(vietnamWall.dateKey, slotHour);
    const { symbol } = ensureSymbolDay(state, vietnamWall.dateKey, base);

    // A retry after this fix also repairs rows written by the legacy broker-wall
    // mapping. Only clear the same symbol/side at its deterministically derived
    // legacy slot, so unrelated appointments remain untouched.
    if (legacyBrokerWall.dateKey === vietnamWall.dateKey) {
      clearLegacyScheduledSignalAtSlot(symbol.alerts, legacySlotHour, slotHour, args.side);
    }

    const existingIndex = symbol.alerts.findIndex((alert) => alert.slotHour === slotHour);
    if (existingIndex >= 0) {
      symbol.alerts[existingIndex] = { ...symbol.alerts[existingIndex], scheduledSignal: args.side };
    } else {
      const decision = cycleDecisionFor(base, vietnamWall.dateKey, slotHour);
      symbol.alerts.push({
        slotHour,
        symbol: String(args.symbol || base).trim().toUpperCase(),
        profile: H1_CLOUD_PROFILE,
        baseSymbol: base,
        baseH1Signal: null,
        baseHour: slotHour,
        baseMinute: 0,
        baseDirection: "",
        symbolH1Signal: null,
        scheduledSignal: args.side,
        postSignalInverted: decision.inverted,
        postSignalRule: decision.rule,
      });
      symbol.alerts.sort((left, right) => left.slotHour - right.slotHour);
    }
    await saveH1CloudState(state);
    await publishH1CloudState(state);
    return { brokerDate: vietnamWall.dateKey, slotHour, base, side: args.side };
  } finally {
    await releaseH1CloudLock(lockToken);
  }
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
