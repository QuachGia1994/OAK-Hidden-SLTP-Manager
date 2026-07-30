import type { SignalEvidence } from "./types";

interface EvidenceSignalRecord {
  date?: unknown;
  hour?: unknown;
  logic_version?: unknown;
  pair_evidence?: Record<string, unknown>;
  pair_entry_times?: Record<string, string | null>;
  pair_entry_states?: Record<string, string | null>;
  pair_signal_states?: Record<string, string | null>;
}

interface EvidenceLookupInput {
  evidenceStore: Record<string, unknown> | null;
  signals: EvidenceSignalRecord[];
  date: string;
  hour: number;
  symbol: string;
  logicVersion: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

/** Resolve evidence embedded in the displayed signal, then use the dedicated store. */
export function resolveSignalEvidence(input: EvidenceLookupInput): SignalEvidence | null {
  const { evidenceStore, signals, date, hour, symbol, logicVersion } = input;
  const signal = signals.find((row) => (
    row.date === date && Number(row.hour) === hour && Number(row.logic_version) === logicVersion
  ));
  const embedded = signal?.pair_evidence?.[symbol];
  if (signal && isRecord(embedded)) {
    return {
      ...embedded,
      logic_version: logicVersion,
      date,
      hour,
      symbol,
      timeframe: typeof embedded.timeframe === "string" ? embedded.timeframe : "M30",
      entry_time: signal.pair_entry_times?.[symbol] ?? null,
      entry_state: signal.pair_entry_states?.[symbol] ?? null,
      signal_state: signal.pair_signal_states?.[symbol] ?? null,
      gbp_entry_time: signal.pair_entry_times?.GBPAUD ?? null,
    } as SignalEvidence;
  }
  const key = `${date}:${hour}:${symbol}:v${logicVersion}`;
  const direct = evidenceStore?.[key];
  if (!isRecord(direct)) return null;
  return {
    ...direct,
    logic_version: logicVersion,
    date,
    hour,
    symbol,
    timeframe: typeof direct.timeframe === "string" ? direct.timeframe : "M30",
  } as SignalEvidence;
}
