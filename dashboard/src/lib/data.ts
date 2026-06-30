import type { Signal, BotState, NewsItem } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

async function fetchJson<T>(url: string, fallback: T): Promise<T> {
  try {
    const res = await fetch(url, { cache: "no-store" });
    if (!res.ok) return fallback;
    return await res.json();
  } catch {
    return fallback;
  }
}

export async function getSignals(): Promise<Signal[]> {
  return fetchJson<Signal[]>(`${API_BASE}/api/signals`, []);
}

export async function getTodaySignals(): Promise<Signal[]> {
  const signals = await getSignals();
  const today = new Date().toISOString().split("T")[0];
  return signals.filter((s) => s.date === today);
}

export async function getBotState(): Promise<BotState | null> {
  return fetchJson<BotState | null>(`${API_BASE}/api/state`, null);
}

export async function getEconomicNews(): Promise<NewsItem[]> {
  return fetchJson<NewsItem[]>(`${API_BASE}/api/news`, []);
}

export async function getSignalsByDate(date: string): Promise<Signal[]> {
  const signals = await getSignals();
  return signals.filter((s) => s.date === date);
}

export async function getAvailableDates(): Promise<string[]> {
  const signals = await getSignals();
  const dates = [...new Set(signals.map((s) => s.date))];
  return dates.sort().reverse();
}
