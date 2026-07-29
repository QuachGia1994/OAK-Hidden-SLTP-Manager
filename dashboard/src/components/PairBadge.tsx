"use client";

import { getSignalLabel } from "@/lib/constants";
import { useLocale } from "./LocaleProvider";

export interface PairBadgeProps {
  pair: string;
  direction: string;
  brokerEntryTime?: string | null;
  localEntryTime?: {
    time: string;
    zoneLabel: string;
    dateDelta: number;
  } | null;
  state?: string | null;
  label?: string | null;
}

export function PairBadge({
  pair,
  direction,
  brokerEntryTime,
  localEntryTime,
  state,
  label,
}: PairBadgeProps) {
  const { locale } = useLocale();

  if (direction === "locked") {
    return (
      <div className="flex items-center justify-between py-1.5">
        <span className="font-mono text-xs font-bold text-[var(--muted)]">{pair}</span>
        <svg className="w-3.5 h-3.5 text-[var(--muted)]/60" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
        </svg>
      </div>
    );
  }

  if (!direction || direction === "-" || direction === "--") {
    return (
      <div className="flex items-center justify-between py-1.5">
        <span className="font-mono text-xs font-semibold text-[var(--muted)]">{pair}</span>
        <span className="text-xs text-[var(--muted)]/60 font-mono">{direction === "--" ? "--" : "—"}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-between py-1.5 gap-2">
      <div className="flex items-center gap-1.5">
        <span className="font-mono text-sm font-black text-[var(--foreground)]">{pair}</span>
        {label && (
          <span className="text-[9px] font-medium font-sans px-1.5 py-0.5 rounded border border-amber-500/30 bg-amber-500/10 text-amber-400">
            {label}
          </span>
        )}
      </div>
      <div className="flex items-center gap-2">
        {state === "DEFERRED_TO_H7" ? (
          <span className="text-[10px] font-mono text-[var(--muted)] italic">Chờ H7</span>
        ) : (
          (localEntryTime || brokerEntryTime) && (
            <div className="flex flex-col items-end leading-tight">
              {localEntryTime ? (
                <span className="font-mono text-xs font-bold text-[var(--foreground)]">
                  {localEntryTime.time} <span className="text-[9px] font-normal text-[var(--muted)]">{localEntryTime.zoneLabel}</span>
                  {localEntryTime.dateDelta !== 0 && (
                    <span className="text-[9px] text-amber-400 ml-0.5">
                      {localEntryTime.dateDelta > 0 ? "+1d" : "-1d"}
                    </span>
                  )}
                </span>
              ) : null}
              {brokerEntryTime ? (
                <span className="font-mono text-[9px] text-[var(--muted)]">
                  {brokerEntryTime} Broker
                </span>
              ) : null}
            </div>
          )
        )}
        <span className={`text-[10px] font-mono font-black tracking-wide px-2.5 py-1 rounded-md border ${
          direction === "BUY"
            ? "border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/15 text-[var(--terminal-accent)]"
            : direction === "SELL"
            ? "border-[var(--terminal-danger)]/30 bg-[var(--terminal-danger)]/15 text-[var(--terminal-danger)]"
            : direction === "SW"
            ? "border-[var(--terminal-warning)]/40 bg-[var(--terminal-warning)]/15 text-[var(--terminal-warning)]"
            : "border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--muted)] font-semibold"
        }`}>
          {state === "DEFERRED_TO_H7" ? "WAIT" : getSignalLabel(direction, locale)}
        </span>
      </div>
    </div>
  );
}
