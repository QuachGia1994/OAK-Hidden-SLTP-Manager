"use client";

import { useMemo, useCallback } from "react";
import type { Signal } from "@/lib/types";
import { ACTIVE_SIGNAL_LOGIC_VERSION, ACTIVE_SIGNAL_PAIRS } from "@/lib/signal-display";
import { useLocale } from "./LocaleProvider";
import { BrokerLocalTime } from "./BrokerLocalTime";
import { hasEvidenceForPair } from "@/lib/signal-evidence";
import { getT } from "@/lib/translations";

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
  const t = getT(locale).evidence;
  const hour = Number(signal.hour);
  const signalTime = signal.signal_time || `${String(hour).padStart(2, "0")}:00`;
  const brokerOffset = typeof signal.broker_utc_offset === "number" ? signal.broker_utc_offset : 3;

  const fetchEvidence = useCallback(
    (symbol: string) => {
      if (onInspect && isVIP && EVIDENCE_SIGNAL_PAIRS.has(symbol) && hasEvidenceForPair(signal, symbol)) {
        onInspect(symbol);
      }
    },
    [onInspect, isVIP, signal]
  );

  const signalState = signal.signal_state || "READY";
  const entryState = signal.entry_state || "READY";
  const isDeactivated = Boolean(signal.deactivated);

  return (
    <div className="terminal-panel rounded-xl p-4 transition-all hover:border-[var(--terminal-accent)]/30 space-y-3">
      {/* HEADER: SLOT & DUAL TIMEZONE */}
      <div className="flex items-center justify-between border-b border-[var(--panel-border)]/60 pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-base font-black text-[var(--foreground)]">
              H{hour}
            </span>
            <span className="text-[10px] font-mono text-[var(--muted)]">
              ({signalTime} Broker)
            </span>
          </div>
          <div className="mt-1 font-mono text-xs">
            <span className="text-[var(--muted)]">Signal: </span>
            <BrokerLocalTime
              brokerTime={signalTime}
              utcIso={typeof signal.signal_at_utc === "string" ? signal.signal_at_utc : null}
              brokerUtcOffset={brokerOffset}
              date={signal.date}
              labelLocal="GMT+7"
              labelBroker="Broker"
            />
          </div>
        </div>

        <div className="text-right font-mono">
          <span
            className={`inline-block rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
              isDeactivated
                ? "bg-[var(--surface-raised)] text-[var(--muted)]"
                : entryState === "READY"
                ? "bg-[var(--terminal-accent)]/15 text-[var(--terminal-accent)] border border-[var(--terminal-accent)]/30"
                : "bg-[var(--terminal-warning)]/15 text-[var(--terminal-warning)] border border-[var(--terminal-warning)]/30"
            }`}
          >
            {isDeactivated ? "OFF" : entryState}
          </span>
          {signal.entry_time && (
            <div className="mt-1 text-[11px] font-bold text-[var(--foreground)]">
              Entry: {signal.entry_time}
            </div>
          )}
        </div>
      </div>

      {/* ACTIVE PAIR ROWS */}
      <div className="space-y-2 font-mono text-xs">
        {ACTIVE_SIGNAL_PAIRS.map((pair) => {
          const dir = signal.pair_dirs?.[pair] || "WAIT";
          const entryTime = signal.pair_entry_times?.[pair] ?? null;
          const entryUtc = signal.pair_entry_at_utc?.[pair] ?? null;
          const isClickable = isVIP && EVIDENCE_SIGNAL_PAIRS.has(pair) && hasEvidenceForPair(signal, pair);
          const isLoading = loadingEvidence === pair;

          const dirColor =
            dir === "BUY" || dir === "Mua"
              ? "var(--terminal-accent)"
              : dir === "SELL" || dir === "Bán"
              ? "var(--terminal-danger)"
              : "var(--muted)";

          return (
            <div
              key={pair}
              className="flex items-center justify-between rounded-lg border border-[var(--panel-border)]/40 bg-[var(--surface-raised)]/40 px-3 py-2"
            >
              <div className="flex items-center gap-2">
                <span className="font-bold text-[var(--foreground)]">{pair}</span>
                <span
                  className="rounded px-1.5 py-0.5 text-[10px] font-black"
                  style={{
                    color: dirColor,
                    backgroundColor: `color-mix(in srgb, ${dirColor} 15%, transparent)`,
                  }}
                >
                  {dir}
                </span>
              </div>

              <div className="flex items-center gap-3">
                <div className="text-right text-[11px]">
                  <BrokerLocalTime
                    brokerTime={entryTime}
                    utcIso={entryUtc}
                    brokerUtcOffset={brokerOffset}
                    date={signal.date}
                    labelLocal="GMT+7"
                    labelBroker="Broker"
                  />
                </div>

                {isClickable && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      fetchEvidence(pair);
                    }}
                    className="flex min-h-9 min-w-9 items-center justify-center rounded bg-[var(--terminal-accent)]/10 px-3 py-1 text-[10px] font-bold text-[var(--terminal-accent)] transition-colors hover:bg-[var(--terminal-accent)]/20"
                  >
                    {isLoading ? t.loading : t.button}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}