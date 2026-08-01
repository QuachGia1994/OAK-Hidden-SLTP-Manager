import type { Signal, BotState, NewsItem, StockAdvisory, DDirectionSnapshotV2 } from "./types";
import { redis, KEYS } from "./redis";
import { ACTIVE_SIGNAL_LOGIC_VERSION, filterDisplayableSignals } from "./constants";
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
    data: filterDisplayableSignals(res.data),
    ok: true,
  };
}

export async function getTodaySignals(): Promise<Signal[]> {
  const res = await getTodaySignalsResult();
  return res.data;
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

export async function getCurrentDDirectionResult(): Promise<DataResult<DDirectionSnapshotV2 | null>> {
  try {
    const raw = await redis.get(KEYS.dDirectionCurrent);
    if (!raw) return { data: null, ok: true };
    const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
    return { data: isCurrentDDirectionSnapshot(parsed) ? parsed as DDirectionSnapshotV2 : null, ok: true };
  } catch (e) {
    console.error("[REDIS READ D-DIRECTION FAILED]", e);
    return { data: null, ok: false, error: "REDIS_READ_FAILED" };
  }
}

export async function getDDirectionByDate(date: string): Promise<DDirectionSnapshotV2 | null> {
  try {
    const raw = await redis.hget(KEYS.dDirectionHistory, date);
    if (!raw) return null;
    const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
    return isCurrentDDirectionSnapshot(parsed) ? parsed as DDirectionSnapshotV2 : null;
  } catch {
    return null;
  }
}

export async function getDDirectionHistoryResult(
  from?: string,
  to?: string
): Promise<Record<string, DDirectionSnapshotV2>> {
  try {
    const historyMap = (await redis.hgetall(KEYS.dDirectionHistory)) as Record<string, unknown> | null;
    if (!historyMap) return {};
    const result: Record<string, DDirectionSnapshotV2> = {};
    for (const [key, raw] of Object.entries(historyMap)) {
      if ((!from || key >= from) && (!to || key <= to)) {
        try {
          const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
          if (isCurrentDDirectionSnapshot(parsed)) result[key] = parsed as DDirectionSnapshotV2;
        } catch {
          // ignore parsing error for corrupted entries
        }
      }
    }
    return result;
  } catch {
    return {};
  }
}

function isCurrentDDirectionSnapshot(value: unknown): value is DDirectionSnapshotV2 {
  if (!value || typeof value !== "object") return false;
  const snapshot = value as Record<string, unknown>;
  return Number(snapshot.logic_version) === ACTIVE_SIGNAL_LOGIC_VERSION
    && Number(snapshot.schema_version) === 9
    && typeof snapshot.target_local_date === "string";
}
