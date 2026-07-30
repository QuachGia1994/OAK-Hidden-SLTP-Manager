"use client";

import { useMemo, useCallback } from "react";
import type { Signal } from "@/lib/types";
import { ACTIVE_SIGNAL_LOGIC_VERSION, ACTIVE_SIGNAL_PAIRS } from "@/lib/signal-display";
import { useLocale } from "./LocaleProvider";
import { PairBadge } from "./PairBadge";
import { hasEvidenceForPair } from "@/lib/signal-evidence";

const EVIDENCE_SIGNAL_PAIRS = new Set(["XAUUSD", "GBPUSD", "GBPAUD"]);

interface SignalCardProps {
  signal: Signal;
  isVIP: boolean;
  redisOk?: boolean;
  brokerNow?: Date;
  onInspect?: (symbol: string) => void;
  loadingEvidence?: string | null;
}

export function SignalCard({ signal, isVIP, onInspect, loadingEvidence }: SignalCardProps) {
  const { locale } = useLocale();
  const hour = Number(signal.hour);
  const isActive = ACTIVE_SIGNAL_LOGIC_VERSION > 0;

  const fetchEvidence = useCallback(
    (symbol: string) => {
      if (onInspect && isVIP && EVIDENCE_SIGNAL_PAIRS.has(symbol) && hasEvidenceForPair(signal, symbol)) {
        onInspect(symbol);
      }
    },
    [onInspect, isVIP, signal],
  );

  const badgeRow = useMemo(
    () =>
      ACTIVE_SIGNAL_PAIRS.map((pair) => {
        const direction = signal.pair_dirs?.[pair] || "WAIT";
        const entryTime = signal.pair_entry_times?.[pair] ?? null;
        const state = signal.pair_entry_states?.[pair] ?? null;
        const label = signal.pair_labels?.[pair] ?? null;
        const isClickable = isVIP && EVIDENCE_SIGNAL_PAIRS.has(pair) && hasEvidenceForPair(signal, pair);
        const isLoading = loadingEvidence === pair;

        return (
          <div key={pair} className="flex items-center gap-1">
            <PairBadge
              pair={pair}
              direction={direction}
              brokerEntryTime={entryTime}
              state={state}
              label={label}
              onClick={isClickable ? () => fetchEvidence(pair) : undefined}
              hasEvidence={isClickable}
            />
            {isLoading && <span className="h-2 w-2 animate-pulse rounded-full bg-[var(--terminal-accent)]" />}
          </div>
        );
      }),
    [signal, isVIP, fetchEvidence, loadingEvidence, locale],
  );

  return (
    <div className="group rounded-xl border border-[var(--terminal-border)] bg-[var(--terminal-bg)]/50 p-2.5 transition-all hover:border-[var(--terminal-accent)]/30 sm:p-3">
      <div className="flex flex-col gap-1.5 sm:gap-2">{badgeRow}</div>
    </div>
  );
}