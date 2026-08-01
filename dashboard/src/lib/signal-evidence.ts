import { ACTIVE_SIGNAL_LOGIC_VERSION } from "./generated-signal-rules.js";
import type { SignalEvidenceUnion } from "./types.ts";
import { isSignalEvidenceV3 } from "./types.ts";

const EVIDENCE_PAIRS = ["XAUUSD"] as const;

export type EvidencePair = (typeof EVIDENCE_PAIRS)[number];

export function isEvidencePair(symbol: string): symbol is EvidencePair {
  return EVIDENCE_PAIRS.includes(symbol as EvidencePair);
}

export type EvidenceFetchResult =
  | { ok: true; evidence: SignalEvidenceUnion }
  | { ok: false; error: string };

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
  evidenceStore?: Record<string, unknown> | null;
  signals: EvidenceSignalRecord[];
  date: string;
  hour: number;
  symbol: string;
  logicVersion: number;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isCurrentXauEvidence(value: unknown, logicVersion: number): value is Record<string, unknown> {
  if (!isRecord(value)) return false;
  return Number(value.evidence_schema_version) === 9
    && Number(value.logic_version) === logicVersion
    && value.symbol === "XAUUSD";
}

/**
 * Resolve signal evidence from a result dict (used by the evidence API route).
 * Supports both options-object style and positional-arguments style for compatibility.
 */
export function resolveSignalEvidence(
  inputOrSignals: EvidenceLookupInput | unknown[],
  date?: string,
  hour?: number,
  symbol?: string,
  version?: number,
): Record<string, unknown> | null {
  if (Array.isArray(inputOrSignals)) {
    if (!date || hour === undefined || symbol !== "XAUUSD") return null;
    const logicVer = version ?? ACTIVE_SIGNAL_LOGIC_VERSION;
    for (const sig of inputOrSignals) {
      if (!sig || typeof sig !== "object") continue;
      const s = sig as Record<string, unknown>;
      if (s["date"] === date && Number(s["hour"]) === hour) {
        const evidence = s["pair_evidence"] as Record<string, unknown> | undefined;
        if (evidence && typeof evidence === "object" && "XAUUSD" in evidence) {
          const ev = evidence.XAUUSD as Record<string, unknown> | undefined;
          if (isCurrentXauEvidence(ev, logicVer)) {
            return { ...ev, date, hour, symbol: "XAUUSD" };
          }
        }
      }
    }
    return null;
  }

  const { evidenceStore, signals, date: d, hour: h, symbol: sym, logicVersion } = inputOrSignals;
  if (sym !== "XAUUSD") return null;
  const signal = Array.isArray(signals) ? signals.find((row) => (
    row.date === d && Number(row.hour) === h && Number(row.logic_version ?? ACTIVE_SIGNAL_LOGIC_VERSION) === logicVersion
  )) : undefined;

  const embedded = signal?.pair_evidence?.XAUUSD;
  if (signal && isCurrentXauEvidence(embedded, logicVersion)) {
    const entryTime = (signal as Record<string, any>).entry_time
      || embedded.entry_time
      || (embedded.entry_timing as any)?.entry_time
      || signal.pair_entry_times?.XAUUSD;
    return {
      ...embedded,
      entry_time: entryTime,
      logic_version: logicVersion,
      date: d,
      hour: h,
      symbol: "XAUUSD",
      evidence_schema_version: 9,
    };
  }

  const key = `${d}:${h}:XAUUSD:v${logicVersion}`;
  const direct = evidenceStore?.[key];
  if (isCurrentXauEvidence(direct, logicVersion)) {
    return {
      ...direct,
      logic_version: logicVersion,
      date: d,
      hour: h,
      symbol: "XAUUSD",
      evidence_schema_version: 9,
    };
  }

  return null;
}

/**
 * Fetch signal evidence for a specific symbol from the dashboard API.
 * Each symbol fetches its own evidence independently.
 */
export async function fetchSignalEvidence(
  date: string,
  hour: number,
  symbol: string,
  version: number = ACTIVE_SIGNAL_LOGIC_VERSION,
): Promise<EvidenceFetchResult> {
  if (!isEvidencePair(symbol)) {
    return { ok: false, error: `Symbol ${symbol} is not in evidence pairs` };
  }
  if (!date || hour === undefined) {
    return { ok: false, error: "Missing date or hour" };
  }

  try {
    const params = new URLSearchParams({
      date,
      hour: String(hour),
      symbol: "XAUUSD",
      version: String(version),
    });
    const res = await fetch(`/api/signals/evidence?${params}`, {
      credentials: "include",
    });
    if (!res.ok) {
      if (res.status === 403) return { ok: false, error: "vip required" };
      if (res.status === 404) return { ok: false, error: "evidence not found" };
      return { ok: false, error: `HTTP ${res.status}` };
    }
    const data = await res.json();
    if (!data || typeof data !== "object") {
      return { ok: false, error: "invalid evidence response" };
    }

    if (isSignalEvidenceV3(data)) {
      return { ok: true, evidence: data };
    }
    const key = `${date}:${hour}:XAUUSD:v${version}`;
    const rawEvidence = data[key] || data;
    if (!rawEvidence || typeof rawEvidence !== "object") {
      return { ok: false, error: "no evidence for this slot" };
    }
    return { ok: true, evidence: rawEvidence as SignalEvidenceUnion };
  } catch (err) {
    const message = err instanceof Error ? err.message : "unknown error";
    return { ok: false, error: `fetch error: ${message}` };
  }
}

/** Get the list of evidence-clickable symbol pairs for a signal. */
export function getEvidencePairs(signal: { pair_evidence?: Record<string, unknown> }): string[] {
  if (!signal.pair_evidence) return [];
  return EVIDENCE_PAIRS.filter((pair) => isCurrentXauEvidence(signal.pair_evidence?.[pair], ACTIVE_SIGNAL_LOGIC_VERSION));
}

/** Whether a pair has evidence data available for the drawer. */
export function hasEvidenceForPair(
  signal: { pair_evidence?: Record<string, unknown> },
  pair: string,
): boolean {
  return pair === "XAUUSD"
    && isCurrentXauEvidence(signal.pair_evidence?.XAUUSD, ACTIVE_SIGNAL_LOGIC_VERSION);
}
