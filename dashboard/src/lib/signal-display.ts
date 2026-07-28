interface SignalDeactivationInput {
  date: string;
  hour: number;
  deactivated?: boolean;
}

/** The dashboard presents signal directions for gold and GBP pairs. */
export const DISPLAYED_SIGNAL_PAIRS = ["XAUUSD", "GBPUSD", "GBPAUD", "XAUUSD2"] as const;

function brokerWeekday(date: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!match) return null;
  const [year, month, day] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const candidate = new Date(Date.UTC(year, month - 1, day));
  if (candidate.getUTCFullYear() !== year || candidate.getUTCMonth() !== month - 1
    || candidate.getUTCDate() !== day) return null;
  return candidate.getUTCDay();
}

export function isEffectivelyDeactivated(signal: SignalDeactivationInput): boolean {
  if (signal.deactivated === true) return true;
  if (signal.hour === 4) return true;
  return signal.hour === 3 && brokerWeekday(signal.date) === 4;
}
