import type { Signal, SlotDisplayState } from "./types";
import { ACTIVE_SIGNAL_LOGIC_VERSION } from "./signal-display";

/**
 * Select the best signal record for a given date and hour from a list of records.
 * Prioritizes active logic version, record revision, and update timestamp.
 * Enforces anti-downgrade rules if an existing record is provided.
 */
export function selectBestSignalRecord(
  records: Signal[],
  date: string,
  hour: number,
  existingRecord?: Signal | null,
): Signal | null {
  const matches = records.filter(
    (r) => r && r.date === date && Number(r.hour) === Number(hour),
  );

  if (matches.length === 0) {
    if (existingRecord && isRealRecord(existingRecord)) {
      return existingRecord; // Protect existing record from dropping to placeholder if Redis missed it
    }
    return null;
  }

  // Sort candidates
  const sorted = [...matches].sort((a, b) => {
    // 1. Matching ACTIVE_SIGNAL_LOGIC_VERSION
    const aVer = Number(a.logic_version || 0);
    const bVer = Number(b.logic_version || 0);
    const targetVer = ACTIVE_SIGNAL_LOGIC_VERSION;

    const aIsTarget = aVer === targetVer ? 1 : 0;
    const bIsTarget = bVer === targetVer ? 1 : 0;
    if (aIsTarget !== bIsTarget) return bIsTarget - aIsTarget;

    if (aVer !== bVer) return bVer - aVer;

    // 2. Highest record_revision
    const aRev = Number(a.record_revision || 0);
    const bRev = Number(b.record_revision || 0);
    if (aRev !== bRev) return bRev - aRev;

    // 3. Most recent state_updated_at_utc
    const aTime = a.state_updated_at_utc ? new Date(a.state_updated_at_utc).getTime() : 0;
    const bTime = b.state_updated_at_utc ? new Date(b.state_updated_at_utc).getTime() : 0;
    if (aTime !== bTime) return bTime - aTime;

    // 4. Most recent ts
    return (b.ts || 0) - (a.ts || 0);
  });

  const best = sorted[0];

  // Anti-downgrade check against existingRecord
  if (existingRecord && isRealRecord(existingRecord)) {
    const existingVer = Number(existingRecord.logic_version || 0);
    const bestVer = Number(best.logic_version || 0);

    // Only allow downgrade if logic_version increases
    if (bestVer <= existingVer) {
      const existingState = getRecordStateRank(existingRecord);
      const bestState = getRecordStateRank(best);

      if (bestState < existingState) {
        return existingRecord;
      }
    }
  }

  return best;
}

export function isRealRecord(s: Signal): boolean {
  return Boolean(s && s.ts !== 0 && (s.entry_state || (s.pair_dirs && Object.keys(s.pair_dirs).length > 0)));
}

function getRecordStateRank(s: Signal): number {
  if (s.terminal_wait) return 5;
  if (s.signal_state === "READY") return 4;
  if (s.signal_state === "PENDING_BASE_CANDLE") return 3;
  if (s.entry_state === "READY") return 2;
  if (s.entry_state === "PENDING_FOLLOWUP") return 1;
  if (s.entry_state === "WAIT") return 0;
  return 0;
}

export interface GetSlotDisplayStateParams {
  brokerNow?: Date | string | null;
  slotDate: string;
  hour: number;
  signal?: Signal | null;
  redisOk?: boolean;
}

/**
 * Resolve the canonical SlotDisplayState for a slot card.
 */
export function getSlotDisplayState(params: GetSlotDisplayStateParams): SlotDisplayState {
  const { brokerNow, slotDate, hour, signal, redisOk = true } = params;

  // Calculate slot start time (H:00 Broker)
  let slotStartTime: Date | null = null;
  try {
    const [year, month, day] = slotDate.split("-").map(Number);
    if (year && month && day) {
      slotStartTime = new Date(Date.UTC(year, month - 1, day, hour, 0, 0));
    }
  } catch {
    slotStartTime = null;
  }

  let nowUtc: Date | null = null;
  if (brokerNow) {
    nowUtc = typeof brokerNow === "string" ? new Date(brokerNow) : brokerNow;
  }

  const isPastOrCurrentSlotTime = Boolean(
    slotStartTime && nowUtc && nowUtc.getTime() >= slotStartTime.getTime(),
  );

  const hasRealRecord = Boolean(signal && isRealRecord(signal));

  // Rule A & B: Redis read failed OR slot time passed but no real record yet -> SYNCING
  if (!redisOk || (isPastOrCurrentSlotTime && !hasRealRecord)) {
    return "SYNCING";
  }

  // Rule A: Before H:00 and no real record -> SCHEDULED
  if (!hasRealRecord) {
    return "SCHEDULED";
  }

  // Real record evaluation
  if (signal) {
    if (signal.terminal_wait) {
      return "WAIT";
    }

    if (signal.entry_state === "PENDING_FOLLOWUP") {
      return "PENDING_ENTRY_FOLLOWUP";
    }

    if (signal.signal_state === "PENDING_BASE_CANDLE") {
      return "PENDING_BASE_CANDLE";
    }

    if (signal.entry_state === "READY" || signal.signal_state === "READY") {
      const dirs = Object.values(signal.pair_dirs || {});
      const hasActivePair = dirs.some((d) => d === "BUY" || d === "SELL");
      const hasWaitPair = dirs.some((d) => d === "WAIT" || !d);

      if (hasActivePair && hasWaitPair) {
        return "PARTIAL_WAIT";
      }
      if (hasActivePair) {
        return "READY";
      }
      return "WAIT";
    }
  }

  return "WAIT";
}
