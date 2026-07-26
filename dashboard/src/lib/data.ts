import type { Signal, BotState, NewsItem, StockAdvisory } from "./types";
import { redis, KEYS } from "./redis";
import { filterDisplayableSignals } from "./constants";

export async function getSignals(): Promise<Signal[]> {
  try {
    const data = await redis.get(KEYS.signals);
    return filterDisplayableSignals((data as Signal[]) || []);
  } catch {
    return [];
  }
}

export async function getTodaySignals(): Promise<Signal[]> {
  // Redis now stores recent signal history as well. The dashboard page
  // is responsible for filtering today's rows from that backlog.
  return getSignals();
}

export function maskSignal(signal: Signal): Signal {
  return {
    ...signal,
    signal: "WAIT",
    pattern_signal: undefined,
    pair_dirs: {},
    entry_prices: {},
    current_prices: {},
    hour_note: null,
    d_direction: null,
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

export function maskStockAdvisory(advisory: StockAdvisory): StockAdvisory {
  return {
    ...advisory,
    signal: { ...advisory.signal, direction: "WAIT" },
    candidates: [],
    backtest: { ...advisory.backtest, hit_rate: 0, mean_aligned_return: 0 },
  };
}
