import "server-only";

import { readRedisReplicas } from "./redis-core";
import {
  H1_CLOUD_STATE_KEY,
  H1_SIGNAL_RULE_VERSION,
  H1_TARGET_BASES,
  buildPublicFeed,
  parseCloudState,
  type H1CloudState,
} from "./h1-cloud-scanner";

export type H1SignalSide = "BUY" | "SELL";
export type H1PostSignalRule = "none" | "cycle-net-invert" | "cycle-net-keep" | "regular-net-invert" | "regular-net-keep" | "weekday-invert" | "weekday-keep";

export type H1SignalSampleBar = {
  brokerDate: string;
  brokerTime: string;
  hour: number;
  minute: number;
  direction: "T" | "G";
  open: number;
  high: number;
  low: number;
  close: number;
  selected: boolean;
};

export type H1SignalAlert = {
  slotHour: number;
  symbol: string;
  profile: string;
  baseSymbol: string;
  baseSignal: H1SignalSide | null;
  baseHour: number | null;
  baseMinute: number | null;
  baseDirection: "T" | "G" | "";
  signal: H1SignalSide | null;
  scheduledSignal: H1SignalSide | null;
  postSignalInverted?: boolean;
  postSignalRule?: H1PostSignalRule;
  entryHour?: number | null;
  patternGroup?: "SW" | "BT" | null;
  patternFamily?: "ALT" | "SAME" | null;
  pattern?: string;
  scannerSource?: "XAUUSD" | "AUDUSD" | "USDJPY" | "GBPUSD" | "";
  inversionBadge?: boolean;
  sampleBars?: H1SignalSampleBar[];
};

export type H1SymbolDay = {
  alerts: H1SignalAlert[];
};

export type H1SignalDay = {
  symbols: Record<string, H1SymbolDay>;
};

export type H1SignalPayload = {
  schemaVersion: number;
  signalRuleVersion?: number;
  profile: string;
  publishedAt: string;
  hours: number[];
  symbols: string[];
  days: Record<string, H1SignalDay>;
};

export const H1_SIGNAL_PUBLIC_SCHEMA = 18;
const LATEST_KEY = "robot-sltp:public:h1-signals:latest";

function vietnamDateKey(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

function parsePayload(raw: unknown, source: string): H1SignalPayload | null {
  if (!raw) return null;
  try {
    const value = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!value || typeof value !== "object") return null;
    const payload = value as Partial<H1SignalPayload>;
    if (
      payload.schemaVersion !== H1_SIGNAL_PUBLIC_SCHEMA
      || payload.signalRuleVersion !== H1_SIGNAL_RULE_VERSION
      || !payload.profile
      || !payload.publishedAt
      || !Array.isArray(payload.hours)
      || !Array.isArray(payload.symbols)
      || payload.symbols.length !== H1_TARGET_BASES.length
      || !H1_TARGET_BASES.every((base, index) => payload.symbols?.[index] === base)
      || !payload.days
      || typeof payload.days !== "object"
    ) {
      console.error("[H1 SIGNAL INVALID PAYLOAD]", source);
      return null;
    }
    return payload as H1SignalPayload;
  } catch (error) {
    console.error("[H1 SIGNAL INVALID PAYLOAD]", source, error instanceof Error ? error.message : String(error));
    return null;
  }
}

export function maskFutureH1Signals(payload: H1SignalPayload | null, today = vietnamDateKey()): H1SignalPayload | null {
  if (!payload) return null;
  return {
    ...payload,
    days: Object.fromEntries(Object.entries(payload.days).filter(([date]) => date <= today)),
  };
}

export type H1SignalsReadResult =
  | { ok: true; data: H1SignalPayload | null }
  | { ok: false };

function payloadFreshness(payload: H1SignalPayload): number {
  const value = Date.parse(payload.publishedAt);
  return Number.isFinite(value) ? value : 0;
}

function freshestPayload(values: Array<H1SignalPayload | null>): H1SignalPayload | null {
  return values.reduce<H1SignalPayload | null>((best, candidate) => {
    if (!candidate) return best;
    if (!best || payloadFreshness(candidate) > payloadFreshness(best)) return candidate;
    return best;
  }, null);
}

function parseCloudStateSafely(raw: unknown, source: string): H1CloudState | null {
  if (!raw) return null;
  try {
    return parseCloudState(raw);
  } catch (error) {
    console.error("[H1 SIGNAL INVALID STATE]", source, error instanceof Error ? error.message : String(error));
    return null;
  }
}

function stateProgress(state: H1CloudState): [string, number, number] {
  const latestDate = Object.keys(state.days).sort().at(-1) || "";
  if (!latestDate) return ["", -1, 0];
  const symbols = Object.values(state.days[latestDate]?.symbols || {});
  const alerts = symbols.flatMap((symbol) => symbol?.alerts || []);
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

function freshestState(values: Array<H1CloudState | null>): H1CloudState | null {
  return values.reduce<H1CloudState | null>((best, candidate) => {
    if (!candidate) return best;
    if (!best || compareStateProgress(candidate, best) > 0) return candidate;
    return best;
  }, null);
}

export async function readLatestH1Signals(): Promise<H1SignalsReadResult> {
  try {
    const latestReplicas = await readRedisReplicas<unknown>(LATEST_KEY);
    const latest = freshestPayload([
      parsePayload(latestReplicas.primary, `${LATEST_KEY}:primary`),
      parsePayload(latestReplicas.backup, `${LATEST_KEY}:backup`),
    ]);
    if (latest) return { ok: true, data: maskFutureH1Signals(latest) };

    const stateReplicas = await readRedisReplicas<unknown>(H1_CLOUD_STATE_KEY);
    const state = freshestState([
      parseCloudStateSafely(stateReplicas.primary, `${H1_CLOUD_STATE_KEY}:primary`),
      parseCloudStateSafely(stateReplicas.backup, `${H1_CLOUD_STATE_KEY}:backup`),
    ]);
    if (!state) return { ok: true, data: null };
    const fallback = parsePayload(buildPublicFeed(state), H1_CLOUD_STATE_KEY);
    return { ok: true, data: maskFutureH1Signals(fallback) };
  } catch (error) {
    console.error("[H1 SIGNAL READ FAILED]", error);
    return { ok: false };
  }
}

export async function getLatestH1Signals(): Promise<H1SignalPayload | null> {
  const result = await readLatestH1Signals();
  return result.ok ? result.data : null;
}
