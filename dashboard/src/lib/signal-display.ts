import { ACTIVE_SIGNAL_LOGIC_VERSION } from "./generated-signal-rules.js";

interface SignalDeactivationInput {
  date: string;
  hour: number;
  deactivated?: boolean;
}

/** The dashboard presents signal directions for gold and GBP pairs. */
export const DISPLAYED_SIGNAL_PAIRS = ["XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD"] as const;
export { ACTIVE_SIGNAL_LOGIC_VERSION };

export function isEffectivelyDeactivated(signal: SignalDeactivationInput): boolean {
  return signal.deactivated === true;
}
