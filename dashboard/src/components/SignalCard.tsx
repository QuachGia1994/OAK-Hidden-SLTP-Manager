"use client";

import { useCallback, useId, useState } from "react";
import type { Signal, HistorySignal } from "@/lib/types";
import { ACTIVE_SIGNAL_LOGIC_VERSION, ACTIVE_SIGNAL_PAIRS } from "@/lib/signal-display";
import { useLocale } from "./LocaleProvider";
import { BrokerLocalTime } from "./BrokerLocalTime";
import { hasEvidenceForPair } from "@/lib/signal-evidence";
import { getT, formatFinalReverseReason } from "@/lib/translations";
import { getWaitReasonForPair, isMissingInputWaitReason, isSignalRecordIncomplete } from "@/lib/signal-integrity";

const EVIDENCE_SIGNAL_PAIRS = new Set(["XAUUSD"]);

type HistorySignalRecord = Signal | HistorySignal;

interface SignalCardProps {
  signal: HistorySignalRecord;
  isVIP: boolean;
  redisOk?: boolean;
  brokerNow?: Date;
  onInspect?: (symbol: string) => void;
  loadingEvidence?: string | null;
}

export function SignalCard({ signal, isVIP, onInspect, loadingEvidence }: SignalCardProps) {
  const { locale } = useLocale();
  const t = getT(locale);
  const [mobileDetailsOpen, setMobileDetailsOpen] = useState(false);
  const pairRowsId = useId();
  const hour = Number(signal.hour);
  const signalTime = signal.signal_time || `${String(hour).padStart(2, "0")}:00`;
  // Legacy records without an offset stay Broker-only; never guess local time.
  const brokerOffset = typeof signal.broker_utc_offset === "number" ? signal.broker_utc_offset : null;
  const brokerClockVerified = signal.broker_clock_verified === true;

  // v88 slot-scoped contract: only the declared applicable pairs are shown.
  // Older v87 5-pair records keep the legacy full row set (never inferred).
  const logicVersion = Number(signal.logic_version || 0);
  const applicablePairs =
    logicVersion >= 88 && Array.isArray(signal.applicable_pairs) && signal.applicable_pairs.length > 0
      ? signal.applicable_pairs
      : ACTIVE_SIGNAL_PAIRS;

  const finalReverseApplied = logicVersion >= 88 && signal.final_reverse_applied === true;
  const reverseReason = finalReverseApplied ? formatFinalReverseReason(signal.final_reverse_reason as string | null | undefined, locale) : null;

  const recordIncomplete = isSignalRecordIncomplete(signal as Record<string, unknown>);

  const fetchEvidence = useCallback(
    (symbol: string) => {
      if (onInspect && isVIP && EVIDENCE_SIGNAL_PAIRS.has(symbol) && hasEvidenceForPair(signal as Record<string, unknown>, symbol)) {
        onInspect(symbol);
      }
    },
    [onInspect, isVIP, signal]
  );

  const signalState = signal.signal_state || "READY";
  const entryState = signal.entry_state || "READY";
  const primaryDirection = signal.pair_dirs?.XAUUSD || signal.signal || "WAIT";
  const primaryDirectionClass =
    primaryDirection === "BUY" || primaryDirection === "Mua"
      ? "border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/10 text-[var(--terminal-accent)]"
      : primaryDirection === "SELL" || primaryDirection === "Bán"
        ? "border-[var(--terminal-danger)]/30 bg-[var(--terminal-danger)]/10 text-[var(--terminal-danger)]"
        : "border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--muted)]";
  const mobileCopy = locale === "EN"
    ? {
        primary: "Primary signal",
        show: "Show pair details",
        hide: "Hide pair details",
        showLabel: `Show ${applicablePairs.length} pair entries for H${hour}`,
        hideLabel: `Hide ${applicablePairs.length} pair entries for H${hour}`,
      }
    : {
        primary: "Tín hiệu chính",
        show: "Xem chi tiết các cặp",
        hide: "Ẩn chi tiết các cặp",
        showLabel: `Xem ${applicablePairs.length} cặp tại H${hour}`,
        hideLabel: `Ẩn ${applicablePairs.length} cặp tại H${hour}`,
      };

  const reverseAppliedToCard = finalReverseApplied
    && Object.values(signal.pair_final_reverse_applied || {}).some(Boolean);

  return (
    <div
      className={`terminal-panel rounded-xl p-4 transition-all hover:border-[var(--terminal-accent)]/30 space-y-3 ${
        reverseAppliedToCard ? "border-[var(--terminal-warning)]/70 ring-1 ring-[var(--terminal-warning)]/25" : ""
      }`}
    >
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
            {reverseAppliedToCard && (
              <span
                className="rounded-md border border-[var(--terminal-warning)]/50 bg-[var(--terminal-warning)]/15 px-2 py-0.5 text-[10px] font-black uppercase tracking-wider text-[var(--terminal-warning)]"
                title={reverseReason || undefined}
              >
                {t.finalReverse.badge}
              </span>
            )}
            {recordIncomplete && (
              <span
                className="rounded-md border border-[var(--terminal-danger)]/40 bg-[var(--terminal-danger)]/10 px-2 py-0.5 text-[10px] font-black uppercase tracking-wider text-[var(--terminal-danger)]"
                title={locale === "EN" ? t.history.missingSource : t.history.missingSource}
              >
                {t.history.missingSource}
              </span>
            )}
          </div>
          <div className="mt-1 font-mono text-xs">
            <span className="text-[var(--muted)]">Signal: </span>
            <BrokerLocalTime
              brokerTime={signalTime}
              utcIso={typeof signal.signal_at_utc === "string" ? signal.signal_at_utc : null}
              brokerUtcOffset={brokerOffset}
              brokerClockVerified={brokerClockVerified}
              localTime={typeof signal.signal_time_local === "string" ? signal.signal_time_local : null}
              date={signal.date}
              labelLocal="GMT+7"
              labelBroker="Broker"
            />
          </div>
        </div>

        <div className="text-right font-mono">
          <span
            className={`inline-block rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
              entryState === "READY"
                ? "bg-[var(--terminal-accent)]/15 text-[var(--terminal-accent)] border border-[var(--terminal-accent)]/30"
                : "bg-[var(--terminal-warning)]/15 text-[var(--terminal-warning)] border border-[var(--terminal-warning)]/30"
            }`}
          >
            {t.signalCard.entry}
          </span>
          {signal.entry_time && (
            <div className="mt-1 text-[11px] font-bold text-[var(--foreground)]">
              <BrokerLocalTime
                brokerTime={signal.entry_time}
                utcIso={typeof signal.entry_at_utc === "string" ? signal.entry_at_utc : null}
                brokerUtcOffset={brokerOffset}
                brokerClockVerified={brokerClockVerified}
                localTime={typeof signal.entry_time_local === "string" ? signal.entry_time_local : null}
                date={signal.date}
                labelLocal="GMT+7"
                labelBroker="Broker"
              />
            </div>
          )}
        </div>
      </div>

      {/* On phones the primary, actionable XAUUSD direction remains visible; the five-row breakdown is opt-in. */}
      <div className="flex items-center justify-between gap-3 rounded-lg border border-[var(--panel-border)]/50 bg-[var(--surface-raised)]/45 px-3 py-2 sm:hidden">
        <div className="min-w-0">
          <div className="text-[10px] font-mono font-bold uppercase tracking-[0.12em] text-[var(--muted)]">
            {mobileCopy.primary}
          </div>
          <div className="mt-0.5 flex items-center gap-2">
            <span className="font-mono text-xs font-black text-[var(--foreground)]">XAUUSD</span>
            <span className={`rounded border px-1.5 py-0.5 font-mono text-[10px] font-black ${primaryDirectionClass}`}>
              {primaryDirection}
            </span>
          </div>
        </div>
      </div>

      <button
        type="button"
        onClick={() => setMobileDetailsOpen((open) => !open)}
        aria-expanded={mobileDetailsOpen}
        aria-controls={pairRowsId}
        aria-label={mobileDetailsOpen ? mobileCopy.hideLabel : mobileCopy.showLabel}
        className="flex min-h-11 w-full items-center justify-between rounded-lg border border-[var(--panel-border)]/60 bg-[var(--surface-raised)]/25 px-3 font-mono text-xs font-bold text-[var(--foreground)] transition-colors hover:border-[var(--terminal-accent)]/45 hover:bg-[var(--terminal-accent)]/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)] sm:hidden"
      >
        <span>{mobileDetailsOpen ? mobileCopy.hide : mobileCopy.show}</span>
        <svg
          viewBox="0 0 24 24"
          className={`h-4 w-4 shrink-0 text-[var(--terminal-accent)] transition-transform ${mobileDetailsOpen ? "rotate-180" : ""}`}
          fill="none"
          aria-hidden="true"
        >
          <path d="m6 9 6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {/* ACTIVE PAIR ROWS */}
      <div id={pairRowsId} className={`space-y-2 font-mono text-xs ${mobileDetailsOpen ? "block" : "hidden"} sm:block`}>
        {applicablePairs.map((pair) => {
          const dir = signal.pair_dirs?.[pair] || "WAIT";
          const waitReason = dir === "WAIT" ? getWaitReasonForPair(signal as Record<string, unknown>, pair) : null;
          const showMissingReason = waitReason !== null && isMissingInputWaitReason(waitReason);
          const isClickable = isVIP && EVIDENCE_SIGNAL_PAIRS.has(pair) && hasEvidenceForPair(signal as Record<string, unknown>, pair);
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
              className={`flex items-center justify-between rounded-lg border px-3 py-2 ${
                showMissingReason
                  ? "border-[var(--terminal-danger)]/35 bg-[var(--terminal-danger)]/[0.05]"
                  : "border-[var(--panel-border)]/40 bg-[var(--surface-raised)]/40"
              }`}
            >
              <div className="flex min-w-0 items-center gap-2">
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
                {showMissingReason && (
                  <span className="truncate font-mono text-[10px] font-bold text-[var(--terminal-warning)]">
                    {t.history.missingSource}: {waitReason}
                  </span>
                )}
              </div>

              {isClickable && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    fetchEvidence(pair);
                  }}
                  className="flex min-h-11 min-w-11 items-center justify-center rounded bg-[var(--terminal-accent)]/10 p-2 text-[16px] text-[var(--terminal-accent)] transition-colors hover:bg-[var(--terminal-accent)]/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)]"
                  aria-label={locale === "EN" ? "View XAUUSD entry evidence" : "Xem bằng chứng Entry XAUUSD"}
                  title={locale === "EN" ? "View XAUUSD entry evidence" : "Xem bằng chứng Entry XAUUSD"}
                >
                  {isLoading ? (
                    <span
                      className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent"
                      aria-hidden="true"
                    />
                  ) : (
                    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" aria-hidden="true">
                      <path d="M5 19V5m0 14h14M8 16v-4m4 4V8m4 8V5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                    </svg>
                  )}
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
