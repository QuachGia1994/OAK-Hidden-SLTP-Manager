"use client";

import { getSignalLabel } from "@/lib/constants";
import { useLocale } from "./LocaleProvider";

interface PairBadgeProps {
  pair: string;
  direction: string;
  entryTime?: string | null;
}

export function PairBadge({ pair, direction, entryTime }: PairBadgeProps) {
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
    <div className="flex items-center justify-between py-1.5">
      <span className="font-mono text-sm font-black text-[var(--foreground)]">{pair}</span>
      <div className="flex items-center gap-2">
        {entryTime && (
          <span className="font-mono text-[10px] text-[var(--muted)]">{entryTime}</span>
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
          {getSignalLabel(direction, locale)}
        </span>
      </div>
    </div>
  );
}
