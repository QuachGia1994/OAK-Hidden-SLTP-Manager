import "server-only";

import { redis } from "./redis-core";

export type H1SignalSide = "BUY" | "SELL";
export type H1DayType = "SW" | "BT";

export type H1SignalAlert = {
  slotHour: number;
  pattern: string;
  bars: string[];
  symbol: string;
  profile: string;
  signal: H1SignalSide | null;
  dayType: H1DayType | null;
  gbpusdSignal: H1SignalSide | null;
  gbpusdBaseHour: number | null;
  gbpusdBaseDirection: "T" | "G" | "";
  gbpusdBlockHour: number | null;
  gbpusdGroup: "Sw" | "Sr" | "Bt" | "";
};

export type H1SymbolDay = {
  dayType: H1DayType | null;
  firstSignalHour: number | null;
  alerts: H1SignalAlert[];
};

export type H1SignalDay = {
  symbols: Record<string, H1SymbolDay>;
};

export type H1SignalPayload = {
  schemaVersion: number;
  profile: string;
  publishedAt: string;
  hours: number[];
  symbols: string[];
  days: Record<string, H1SignalDay>;
};

export const H1_SIGNAL_PUBLIC_SCHEMA = 1;
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

export async function getLatestH1Signals(): Promise<H1SignalPayload | null> {
  try {
    return parsePayload(await redis.get(LATEST_KEY), LATEST_KEY);
  } catch (error) {
    console.error("[H1 SIGNAL READ FAILED]", error);
    return null;
  }
}
