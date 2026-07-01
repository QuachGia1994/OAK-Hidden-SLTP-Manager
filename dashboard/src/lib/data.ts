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
  const signals = await getSignals();
  const today = new Date().toISOString().split("T")[0];
  return signals.filter((s) => s.date === today);
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
