import "server-only";

import {
  H1_CLOUD_PROFILE,
  H1_PUBLIC_SYMBOLS,
  H1_SCAN_HOURS,
  H1_SIGNAL_RULE_VERSION,
} from "./h1-cloud-scanner";

export type H1SignalSide = "BUY" | "SELL";
export type H1PostSignalRule = "none";

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
  baseSignal: null;
  baseHour: number | null;
  baseMinute: number | null;
  baseDirection: "";
  signal: null;
  scheduledSignal: H1SignalSide | null;
  postSignalInverted?: false;
  postSignalRule?: H1PostSignalRule;
  entryHour?: null;
  patternGroup?: null;
  patternFamily?: null;
  pattern?: "";
  scannerSource?: "";
  inversionBadge?: false;
  sampleBars?: [];
  signalBaseBar?: null;
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
const H1_STATIC_HISTORY_CALENDAR_DAYS = 90;

function vietnamDateKey(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

function addIsoDays(dateKey: string, delta: number): string {
  const [year, month, day] = dateKey.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day + delta)).toISOString().slice(0, 10);
}

function weekday(dateKey: string): number {
  return new Date(`${dateKey}T12:00:00Z`).getUTCDay();
}

function staticSchedulePayload(today = vietnamDateKey()): H1SignalPayload {
  const days: Record<string, H1SignalDay> = {};
  for (let offset = H1_STATIC_HISTORY_CALENDAR_DAYS - 1; offset >= 0; offset -= 1) {
    const date = addIsoDays(today, -offset);
    const day = weekday(date);
    if (day === 0 || day === 6) continue;
    days[date] = {
      symbols: Object.fromEntries(H1_PUBLIC_SYMBOLS.map((symbol) => [symbol, { alerts: [] }])),
    };
  }
  return {
    schemaVersion: H1_SIGNAL_PUBLIC_SCHEMA,
    signalRuleVersion: H1_SIGNAL_RULE_VERSION,
    profile: H1_CLOUD_PROFILE,
    publishedAt: new Date().toISOString(),
    hours: [...H1_SCAN_HOURS],
    symbols: [...H1_PUBLIC_SYMBOLS],
    days,
  };
}

export function maskFutureH1Signals(payload: H1SignalPayload | null, today = vietnamDateKey()): H1SignalPayload | null {
  if (!payload) return null;
  return {
    ...payload,
    days: Object.fromEntries(Object.entries(payload.days).filter(([date]) => date <= today)),
  };
}

export type H1SignalsReadResult = { ok: true; data: H1SignalPayload };

export async function readLatestH1Signals(): Promise<H1SignalsReadResult> {
  return { ok: true, data: staticSchedulePayload() };
}

export async function getLatestH1Signals(): Promise<H1SignalPayload> {
  return staticSchedulePayload();
}
