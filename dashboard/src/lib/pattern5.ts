import "server-only";

import { ENGINE5_ACTIVE_SYMBOLS, filterActiveEngine5Tables } from "./engine5-symbols";
import { redis } from "./redis-core";

export type Pattern5Candle = {
  index: number;
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  direction: "T" | "G";
};

export type Pattern5Group = "Sr" | "Sw" | "Bt";

export type Pattern5Signal = {
  group: Pattern5Group;
  baseSignal: "BUY" | "SELL" | null;
  signal: "BUY" | "SELL" | null;
  reversed: boolean;
  label: string;
  pattern: string;
  evidence: Pattern5Candle[];
  locked?: boolean;
};

export type Pattern5Day = {
  name: string;
  date: string;
  display: string;
};

export type Pattern5Reference = {
  date: string;
  display: string;
  group: Pattern5Group;
  pattern: string;
};

export type Pattern5Table = {
  base: string;
  symbol: string | null;
  sourceProfile?: string;
  error?: string;
  days?: Pattern5Day[];
  rows?: Record<string, Array<Pattern5Signal | "">>;
  detail?: Record<string, string[]>;
  h15Reference?: Pattern5Reference;
};
export type Pattern5Payload = {
  schemaVersion: number;
  activeSymbols?: string[];
  profile: string;
  weekStart: string;
  blocks: number[];
  tables: Pattern5Table[];
  cacheHit?: boolean;
  publishedAt?: string;
};

export const PATTERN5_PUBLIC_SCHEMA = 14;
const LATEST_KEY = "robot-sltp:public:pattern5:latest";

export function filterActivePattern5(payload: Pattern5Payload | null): Pattern5Payload | null {
  if (!payload) return null;
  return {
    ...payload,
    activeSymbols: [...ENGINE5_ACTIVE_SYMBOLS],
    tables: filterActiveEngine5Tables(payload.tables),
  };
}

function vietnamDateKey(now = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Ho_Chi_Minh",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(now);
}

export function maskFuturePattern5(payload: Pattern5Payload | null, today = vietnamDateKey()): Pattern5Payload | null {
  if (!payload) return null;
  return {
    ...payload,
    tables: payload.tables.map((table) => {
      const days = table.days ?? [];
      const isFutureIndex = (index: number) => Boolean(days[index]?.date && days[index]!.date > today);
      return {
        ...table,
        rows: table.rows
          ? Object.fromEntries(Object.entries(table.rows).map(([block, items]) => [
              block,
              items.map((item, index) => isFutureIndex(index) ? "" : item),
            ]))
          : undefined,
        detail: table.detail
          ? Object.fromEntries(Object.entries(table.detail).map(([block, items]) => [
              block,
              items.map((item, index) => isFutureIndex(index) ? "" : item),
            ]))
          : undefined,
      };
    }),
  };
}

function parsePayload(raw: unknown, source: string): Pattern5Payload | null {
  if (!raw) return null;
  try {
    const value = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!value || typeof value !== "object") {
      console.error("[PATTERN5 INVALID PAYLOAD]", source, "not an object");
      return null;
    }
    const payload = value as Partial<Pattern5Payload>;
    if (payload.schemaVersion !== PATTERN5_PUBLIC_SCHEMA || !payload.profile || !payload.weekStart || !Array.isArray(payload.blocks) || !Array.isArray(payload.tables)) {
      console.error("[PATTERN5 INVALID PAYLOAD]", source, `expected schema ${PATTERN5_PUBLIC_SCHEMA}, received ${String(payload.schemaVersion)}`);
      return null;
    }
    return payload as Pattern5Payload;
  } catch (error) {
    console.error("[PATTERN5 INVALID PAYLOAD]", source, error instanceof Error ? error.message : String(error));
    return null;
  }
}
export async function getPattern5Profile(profile: string): Promise<Pattern5Payload | null> {
  if (!profile.trim()) return null;
  try {
    const key = `robot-sltp:public:pattern5:${profile.trim()}`;
    return parsePayload(await redis.get(key), key);
  } catch (error) {
    console.error("[PATTERN5 PROFILE READ FAILED]", profile, error);
    return null;
  }
}

export async function getLatestPattern5(): Promise<Pattern5Payload | null> {
  const keys = [
    LATEST_KEY,
    process.env.PATTERN5_PUBLIC_PROFILE
      ? `robot-sltp:public:pattern5:${process.env.PATTERN5_PUBLIC_PROFILE}`
      : "",
    "robot-sltp:public:pattern5:Vantage",
    "robot-sltp:public:pattern5:VantageDemo",
  ].filter(Boolean);

  for (const key of keys) {
    try {
      const payload = parsePayload(await redis.get(key), key);
      if (payload) return payload;
    } catch (error) {
      console.error("[PATTERN5 READ FAILED]", key, error);
    }
  }
  return null;
}
