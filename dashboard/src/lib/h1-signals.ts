import "server-only";

import { redis } from "./redis-core";
import { H1_SIGNAL_RULE_VERSION, reconcileTradeState, type H1LookbackAction } from "./h1-cloud-scanner";

export type H1SignalSide = "BUY" | "SELL";
export type H1PatternKind = "pattern1" | "pattern2" | "pattern3" | "pattern4" | "pattern5";
export type H1ScannerBase = "XAUUSD" | "GBPUSD" | "AUDUSD" | "USDCAD" | "USDJPY";
export type H1PostSignalRule = "none" | "thu-cycle" | "fri-cycle";

export type H1SignalAlert = {
  slotHour: number;
  pattern: string;
  patternKind: H1PatternKind;
  bars: string[];
  symbol: string;
  profile: string;
  scannerBase: H1ScannerBase;
  scannerSymbol: string;
  baseSymbol: string;
  baseSignal: H1SignalSide | null;
  baseHour: number | null;
  baseDirection: "T" | "G" | "";
  signal: H1SignalSide | null;
  postSignalInverted?: boolean;
  postSignalRule?: H1PostSignalRule;
  lookbackPattern?: string | null;
  lookbackAction?: H1LookbackAction;
  tradeAllowed?: boolean;
};

export type H1SymbolDay = {
  alerts: H1SignalAlert[];
  blockedSlots?: number[];
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

export const H1_SIGNAL_PUBLIC_SCHEMA = 7;
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

export function normalizeTradeStatePayload(payload: H1SignalPayload | null): H1SignalPayload | null {
  if (!payload) return null;
  return {
    ...payload,
    days: Object.fromEntries(Object.entries(payload.days).map(([date, day]) => [
      date,
      {
        ...day,
        symbols: Object.fromEntries(Object.entries(day.symbols).map(([base, source]) => {
          const state = {
            alerts: source.alerts.map((alert) => ({ ...alert })),
            blockedSlots: [...(source.blockedSlots || [])],
          };
          reconcileTradeState(state);
          return [base, state];
        })),
      },
    ])),
  };
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
    return normalizeTradeStatePayload(parsePayload(await redis.get(LATEST_KEY), LATEST_KEY));
  } catch (error) {
    console.error("[H1 SIGNAL READ FAILED]", error);
    return null;
  }
}
