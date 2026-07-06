import type { Signal, BotState, NewsItem } from "./types";
import { redis, KEYS } from "./redis";

export async function getSignals(): Promise<Signal[]> {
  try {
    const data = await redis.get(KEYS.signals);
    return (data as Signal[]) || [];
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
    pair_dirs: {},
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
