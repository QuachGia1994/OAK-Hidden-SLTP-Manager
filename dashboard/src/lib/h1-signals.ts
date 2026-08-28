import "server-only";

import { redis } from "./redis-core";
import { H1_SIGNAL_RULE_VERSION } from "./h1-cloud-scanner";

export type H1SignalSide = "BUY" | "SELL";
export type H1PostSignalRule = "none" | "cycle-net-invert" | "cycle-net-keep" | "regular-net-invert" | "regular-net-keep";

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

export const H1_SIGNAL_PUBLIC_SCHEMA = 17;
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

export async function readLatestH1Signals(): Promise<H1SignalsReadResult> {
  try {
    return { ok: true, data: maskFutureH1Signals(parsePayload(await redis.get(LATEST_KEY), LATEST_KEY)) };
  } catch (error) {
    console.error("[H1 SIGNAL READ FAILED]", error);
    return { ok: false };
  }
}

export async function getLatestH1Signals(): Promise<H1SignalPayload | null> {
  const result = await readLatestH1Signals();
  return result.ok ? result.data : null;
}
