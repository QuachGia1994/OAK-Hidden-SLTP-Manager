"use client";

import { getSignalLabel } from "@/lib/constants";
import { useLocale } from "./LocaleProvider";

interface PairBadgeProps {
  pair: string;
  direction: string;
}

export function PairBadge({ pair, direction }: PairBadgeProps) {
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

  if (pair === "Stock-DIRECTION" || pair === "GBP-DIRECTION") {
    const isBuy = direction === "BUY";
    const isGBP = pair === "GBP-DIRECTION";
    const borderColor = "border-[var(--panel-border)]";
    const bgColor = "bg-[var(--surface-raised)]";
    const textColor = "text-[var(--foreground)]";
    const iconBg = isGBP ? "bg-[var(--terminal-accent)]/15 text-[var(--terminal-accent)]" : "bg-[var(--terminal-warning)]/15 text-[var(--terminal-warning)]";
    return (
      <div
        data-tone={isGBP ? "gbp" : "stock"}
        className={`direction-badge my-2 flex items-center justify-between gap-2 rounded-xl border ${borderColor} ${bgColor} px-3 py-2`}
      >
        <span className={`inline-flex items-center gap-2 font-mono text-[11px] font-black tracking-wide ${textColor}`}>
          <span className={`grid h-5 w-5 place-items-center rounded-lg ${iconBg}`}>
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M7 7h10v10M17 7 7 17" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          {pair}
        </span>
        <span className={`text-[10px] font-mono font-black tracking-wide px-2.5 py-1 rounded-md border ${
          isBuy
            ? "border-[var(--terminal-accent)]/40 bg-[var(--terminal-accent)]/15 text-[var(--terminal-accent)]"
            : "border-[var(--terminal-danger)]/40 bg-[var(--terminal-danger)]/15 text-[var(--terminal-danger)]"
        }`}>
          {getSignalLabel(direction, locale)}
        </span>
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

  if (direction === "SW") {
    return (
      <div className="flex items-center justify-between py-1.5">
        <span className="font-mono text-sm font-black text-[var(--foreground)]">{pair}</span>
        <span className="text-[10px] font-mono font-black tracking-wide px-2.5 py-1 rounded-md border border-[var(--terminal-warning)]/40 bg-[var(--terminal-warning)]/15 text-[var(--terminal-warning)]">
          {getSignalLabel(direction, locale)}
        </span>
      </div>
    );
  }

  if (direction === "BT") {
    return (
      <div className="flex items-center justify-between py-1.5">
        <span className="font-mono text-sm font-black text-[var(--foreground)]">{pair}</span>
        <span className="text-[10px] font-mono font-black tracking-wide px-2.5 py-1 rounded-md border border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--foreground)]">
          {getSignalLabel(direction, locale)}
        </span>
      </div>
    );
  }

  if (direction === "WAIT") {
    return (
      <div className="flex items-center justify-between py-1.5">
        <span className="font-mono text-sm font-black text-[var(--foreground)]">{pair}</span>
        <span className="text-[10px] font-mono font-black tracking-wide px-2.5 py-1 rounded-md border border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--muted)] font-semibold">
          {getSignalLabel(direction, locale)}
        </span>
      </div>
    );
  }

  const isBuy = direction === "BUY";

  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="font-mono text-sm font-black text-[var(--foreground)]">{pair}</span>
      <span className={`text-[10px] font-mono font-black tracking-wide px-2.5 py-1 rounded-md border ${isBuy ? "border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/15 text-[var(--terminal-accent)]" : "border-[var(--terminal-danger)]/30 bg-[var(--terminal-danger)]/15 text-[var(--terminal-danger)]"}`}>
        {getSignalLabel(direction, locale)}
      </span>
    </div>
  );
}
