import { ACTIVE_SIGNAL_LOGIC_VERSION } from "./generated-signal-rules.js";

interface SignalDeactivationInput {
  date: string;
  hour: number;
  deactivated?: boolean;
}

interface SignalPairReadinessInput {
  pair_dirs?: Record<string, string>;
  pair_entry_times?: Record<string, string | null>;
  pair_entry_states?: Record<string, string | null>;
}

const VALID_ENTRY_TIME = /^\d{2}:\d{2}$/;

/** The dashboard presents signal directions for gold and GBP pairs. */
export const ACTIVE_SIGNAL_PAIRS = ["XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD"] as const;
export const DISABLED_SIGNAL_PAIRS = [] as const;
export const DISPLAYED_SIGNAL_PAIRS = ["XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD"] as const;
export { ACTIVE_SIGNAL_LOGIC_VERSION };

export function isEffectivelyDeactivated(signal: SignalDeactivationInput): boolean {
  return signal.deactivated === true;
}

/** A pair is tradable only when its direction and validated entry are both ready. */
export function isSignalPairReady(signal: SignalPairReadinessInput, symbol: string): boolean {
  if ((DISABLED_SIGNAL_PAIRS as readonly string[]).includes(symbol)) return false;
  const direction = signal.pair_dirs?.[symbol];
  const entryTime = signal.pair_entry_times?.[symbol];
  return (
    (direction === "BUY" || direction === "SELL")
    && signal.pair_entry_states?.[symbol] === "READY"
    && VALID_ENTRY_TIME.test(entryTime || "")
  );
}

export function countReadySignalPairs(signal: SignalPairReadinessInput): number {
  return ACTIVE_SIGNAL_PAIRS.filter((symbol) => isSignalPairReady(signal, symbol)).length;
}

/** Remove every actionable or evidentiary field from a public signal payload. */
export function maskSignalForPublic(signal: Record<string, unknown>) {
  const waitDirections = Object.fromEntries(DISPLAYED_SIGNAL_PAIRS.map((symbol) => [symbol, "WAIT"]));
  const waitStates = Object.fromEntries(DISPLAYED_SIGNAL_PAIRS.map((symbol) => [symbol, "WAIT"]));
  const emptyEntries = Object.fromEntries(DISPLAYED_SIGNAL_PAIRS.map((symbol) => [symbol, null]));
  return {
    ...signal,
    signal: "WAIT",
    signal_state: "WAIT",
    entry_time: null,
    entry_time_local: null,
    entry_at_utc: null,
    entry_candidate: null,
    entry_rule: null,
    entry_state: "WAIT",
    pattern_signal: undefined,
    pair_dirs: waitDirections,
    pair_signal_states: waitStates,
    pair_entry_times: emptyEntries,
    pair_entry_states: waitStates,
    pair_entry_at_utc: {},
    pair_groups: {},
    pair_labels: {},
    pair_evidence: undefined,
    entry_prices: {},
    current_prices: {},
    hour_note: null,
  };
}
