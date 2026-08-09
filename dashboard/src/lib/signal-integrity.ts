/**
 * History rebuild integrity helpers.
 *
 * The bot now tags every rebuilt record with a per-pair `wait_reasons` map and
 * a `rebuild_state` of READY / REBUILD_INCOMPLETE.  A record is "incomplete"
 * when any applicable pair WAITs for a missing input (no H1/D candle, ambiguous
 * source, unverified clock, …).  The dashboard must never present those slots
 * as a fully computed archive, so it surfaces an integrity warning instead.
 */

/** WAIT reasons that still complete a rebuilt slot (directionless candle, out of scope,
 *  or a slot whose required candles predate the broker's weekly market open). */
export const VALID_WAIT_REASONS = new Set([
  "H49_H1_DOJI",
  "D_H4_DOJI",
  "M30_LAYER_DOJI",
  "NOT_APPLICABLE",
  "MARKET_CLOSED_WEEK_OPEN",
]);

/** WAIT reasons that mean the slot cannot be published as complete history. */
export const MISSING_INPUT_WAIT_REASONS = new Set([
  "H49_H1_MISSING",
  "H49_H1_AMBIGUOUS",
  "H16_H1_MISSING",
  "D_H4_MISSING",
  "D_H4_AMBIGUOUS",
  "M30_LAYER2_MISSING",
  "M30_LAYER3_MISSING",
  "CLOCK_OFFSET_UNVERIFIED",
  "ACTIVE_SOURCE_MISSING",
  "D_SNAPSHOT_NOT_PUBLISHED",
  "WRONG_SESSION_DATE",
  "WAIT_MT5_DATA",
  "MT5_SYMBOL_UNAVAILABLE",
  "MT5_HISTORY_UNAVAILABLE",
  "MT5_CONNECTION_UNAVAILABLE",
  "BROKER_OFFSET_UNVERIFIED",
]);

export function isMissingInputWaitReason(reason: string | null | undefined): boolean {
  return typeof reason === "string" && MISSING_INPUT_WAIT_REASONS.has(reason);
}

export function isValidWaitReason(reason: string | null | undefined): boolean {
  return typeof reason === "string" && VALID_WAIT_REASONS.has(reason);
}

export interface SignalIntegrityInput {
  rebuild_state?: string | null;
  rebuild_state_reason?: string | null;
  signal?: string | null;
  signal_state?: string | null;
  entry_state?: string | null;
  failure_reason?: string | null;
  pair_dirs?: Record<string, string>;
  pair_signal_states?: Record<string, string | null>;
  wait_reasons?: Record<string, string>;
  applicable_pairs?: string[];
}

/** Explicit wait reason for a pair, falling back to the record-level failure reason. */
export function getWaitReasonForPair(
  signal: SignalIntegrityInput,
  pair: string,
): string | null {
  const reason = signal.wait_reasons?.[pair];
  if (typeof reason === "string" && reason) return reason;
  if (signal.failure_reason && (signal.pair_dirs?.[pair] === "WAIT" || signal.pair_signal_states?.[pair] === "WAIT")) {
    return signal.failure_reason;
  }
  return null;
}

/**
 * A history record is incomplete when the rebuild could not resolve every
 * required input.  DOJI / NOT_APPLICABLE waits are legitimate and do not flag.
 */
export function isSignalRecordIncomplete(signal: SignalIntegrityInput): boolean {
  if (signal.rebuild_state === "REBUILD_INCOMPLETE") return true;
  if (signal.rebuild_state === "MISSING_INPUT") return true;
  const pairs = signal.pair_dirs || {};
  for (const pair of Object.keys(pairs)) {
    const state = signal.pair_signal_states?.[pair];
    if (state !== "WAIT" && pairs[pair] !== "WAIT") continue;
    if (isMissingInputWaitReason(getWaitReasonForPair(signal, pair))) return true;
  }
  // Legacy records (no per-pair wait_reasons) fall back to the record-level
  // failure_reason.  Once a pair-level wait_reasons map exists it is
  // authoritative, so the record-level fallback must not re-flag a record
  // whose pair reasons were all reclassified as valid (e.g. Monday week-open
  // MARKET_CLOSED_WEEK_OPEN with a stale WAIT_MT5_DATA failure_reason).
  const waitReasons = signal.wait_reasons || {};
  if (Object.keys(waitReasons).length === 0
    && (signal.signal_state === "WAIT" || signal.entry_state === "WAIT")
    && isMissingInputWaitReason(signal.failure_reason)) {
    return true;
  }
  return false;
}

export function countIncompleteSignals(signals: readonly SignalIntegrityInput[]): number {
  return signals.filter((signal) => isSignalRecordIncomplete(signal)).length;
}

/** Human-safe default reason label for an unknown WAIT token. */
export function formatWaitReason(reason: string | null | undefined): string {
  return reason || "WAIT_NO_REASON";
}
