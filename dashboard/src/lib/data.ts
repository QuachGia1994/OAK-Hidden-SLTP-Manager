import type { Signal, BotState, NewsItem, StockAdvisory } from "./types";
import { redis, KEYS } from "./redis";
import { isActiveSignalHour } from "./constants";
export { maskStockAdvisory } from "./stock-advisor-display";

export interface DataResult<T> {
  data: T;
  ok: boolean;
  error?: string;
}

export async function getSignalsResult(): Promise<DataResult<Signal[]>> {
  try {
    const data = await redis.get(KEYS.signals);
    if (!data) return { data: [], ok: true };
    return { data: data as Signal[], ok: true };
  } catch (e) {
    console.error("[REDIS READ FAILED]", e);
    return { data: [], ok: false, error: "REDIS_READ_FAILED" };
  }
}

export async function getSignals(): Promise<Signal[]> {
  const res = await getSignalsResult();
  return res.data;
}

/** Return all signals for active hours (including WAIT) — dashboard fills missing hours itself. */
export async function getTodaySignalsResult(): Promise<DataResult<Signal[]>> {
  const res = await getSignalsResult();
  if (!res.ok) return res;
  return {
    data: res.data.filter((s) => isActiveSignalHour(s.hour)),
    ok: true,
  };
}

export async function getTodaySignals(): Promise<Signal[]> {
  const res = await getTodaySignalsResult();
  return res.data;
}

export function maskSignal(signal: Signal): Signal {
  return {
    ...signal,
    signal: "WAIT",
    pattern_signal: undefined,
    pair_dirs: { XAUUSD: "WAIT", GBPUSD: "WAIT", GBPAUD: "WAIT", GBPJPY: "WAIT", GBPCAD: "WAIT" },
    entry_prices: {},
    current_prices: {},
    hour_note: null,
  };
}

export async function getBotState(): Promise<BotState | null> {
  try {
    const data = await redis.get(KEYS.state);
    return (data as BotState) || null;
  } catch {
    return null;
  }
}

export async function getEconomicNews(): Promise<NewsItem[]> {
  try {
    const data = await redis.get(KEYS.news);
    return (data as NewsItem[]) || [];
  } catch {
    return [];
  }
}

export async function getStockAdvisory(): Promise<StockAdvisory | null> {
  try {
    return (await redis.get(KEYS.stockAdvisor)) as StockAdvisory | null;
  } catch {
    return null;
  }
}

