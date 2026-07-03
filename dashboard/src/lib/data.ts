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
  // Bot push_to_dashboard() đã filter theo ngày trước khi ghi Redis,
  // nên Redis chỉ chứa signal hôm nay. Không cần filter lại ở đây —
  // việc filter bằng UTC trên Next.js server gây lệch ngày so với
  // datetime.now() (local) bên Python bot.
  return getSignals();
}

export function maskSignal(signal: Signal): Signal {
  return {
    ...signal,
    signal: "WAIT",
    pair_dirs: {},
    entry_time: null,
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
