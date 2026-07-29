import type { Signal, BotState, NewsItem, StockAdvisory } from "./types";
import { redis, KEYS } from "./redis";
import { isActiveSignalHour } from "./constants";
export { maskStockAdvisory } from "./stock-advisor-display";

export async function getSignals(): Promise<Signal[]> {
  try {
    const data = await redis.get(KEYS.signals);
    return (data as Signal[]) || [];
  } catch {
    return [];
  }
}

/** Return all signals for active hours (including WAIT) — dashboard fills missing hours itself. */
export async function getTodaySignals(): Promise<Signal[]> {
  const all = await getSignals();
  return all.filter((s) => isActiveSignalHour(s.hour));
}

export function maskSignal(signal: Signal): Signal {
  return {
    ...signal,
    signal: "WAIT",
    pattern_signal: undefined,
    pair_dirs: { XAUUSD: "WAIT", GBPUSD: "WAIT", GBPAUD: "WAIT" },
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

