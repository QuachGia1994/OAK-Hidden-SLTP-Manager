import "server-only";

import { redis } from "./redis";

export type Pattern5Signal = {
  group: "Sw" | "Bt";
  signal: "BUY" | "SELL";
  label: string;
  pattern: number;
  mirrored: boolean;
};

export type Pattern5Day = {
  name: string;
  date: string;
  display: string;
};

export type Pattern5Table = {
  base: string;
  symbol: string | null;
  error?: string;
  days?: Pattern5Day[];
  rows?: Record<string, Array<Pattern5Signal | "">>;
  detail?: Record<string, string[]>;
};
export type Pattern5Payload = {
  profile: string;
  weekStart: string;
  blocks: number[];
  tables: Pattern5Table[];
  cacheHit?: boolean;
  publishedAt?: string;
};

const LATEST_KEY = "robot-sltp:public:pattern5:latest";

function parsePayload(raw: unknown): Pattern5Payload | null {
  if (!raw) return null;
  try {
    const value = typeof raw === "string" ? JSON.parse(raw) : raw;
    if (!value || typeof value !== "object") return null;
    const payload = value as Partial<Pattern5Payload>;
    if (!payload.profile || !payload.weekStart || !Array.isArray(payload.blocks) || !Array.isArray(payload.tables)) {
      return null;
    }
    return payload as Pattern5Payload;
  } catch {
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
      const payload = parsePayload(await redis.get(key));
      if (payload) return payload;
    } catch (error) {
      console.error("[PATTERN5 READ FAILED]", key, error);
    }
  }
  return null;
}
