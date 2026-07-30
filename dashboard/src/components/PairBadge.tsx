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
  onClick?: () => void;
  hasEvidence?: boolean;
}

export function PairBadge({
  pair,
  direction,
  brokerEntryTime,
  localEntryTime,
  state,
  label,
  onClick,
  hasEvidence,
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

  const baseColors: Record<string, string> = {
    BUY: "border-[var(--terminal-accent)]/20 bg-[var(--terminal-accent)]/5",
    SELL: "border-[var(--terminal-danger)]/20 bg-[var(--terminal-danger)]/5",
    WAIT: "border-[var(--panel-border)] bg-[var(--surface-raised)]",
    SW: "border-[var(--terminal-warning)]/20 bg-[var(--terminal-warning)]/5",
  };

  const canOpenEvidence = Boolean(hasEvidence && onClick);

  const Wrapper = canOpenEvidence ? "button" : "div";
  const wrapperProps = canOpenEvidence
    ? {
        type: "button" as const,
        onClick: onClick,
        "aria-label": locale === "VN" 
          ? `Xem bằng chứng M30 ${pair}`
          : `View M30 evidence for ${pair}`,
      }
    : {
        "aria-label": `${direction} signal for ${pair}`
      };

  return (
    <Wrapper
      {...wrapperProps}
      className={`relative group flex items-center justify-between w-full p-2.5 rounded border transition-all text-left overflow-hidden ${
        canOpenEvidence ? "cursor-pointer hover:border-[var(--terminal-accent)]/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)]/70" : ""
      } ${baseColors[direction] || baseColors.WAIT}`}
    >
      <div className="relative z-10 flex items-center justify-between w-full">
        <div className="flex flex-col items-start min-w-0">
          <div className="flex items-center gap-1.5 min-w-0">
            <span className="font-mono text-sm font-bold tracking-tight text-[var(--foreground)] truncate">
              {pair}
            </span>
            {label && (
              <span className="rounded border border-[var(--panel-border)] bg-[var(--surface)] px-1.5 py-0.5 font-mono text-[10px] font-bold text-[var(--muted)]">
                {label}
              </span>
            )}
            {canOpenEvidence && (
              <ChartLine className="w-3.5 h-3.5 text-[var(--muted)] group-hover:text-[var(--terminal-accent)] transition-colors shrink-0" />
            )}
          </div>
          {localEntryTime ? (
            <div className="flex items-center gap-1.5 mt-0.5 min-w-0">
              <span className="text-[11px] font-mono font-medium text-[var(--muted)] whitespace-nowrap">
                {brokerEntryTime}
              </span>
              <span className="text-[10px] text-[var(--muted)]/50">•</span>
              <span className="text-[11px] font-mono text-[var(--muted)] truncate">
                {localEntryTime.time} {localEntryTime.zoneLabel}
                {localEntryTime.dateDelta !== 0 && (
                  <sup className="ml-0.5 text-[9px] text-[var(--muted)]/70">
                    {localEntryTime.dateDelta > 0 ? `+${localEntryTime.dateDelta}` : localEntryTime.dateDelta}
                  </sup>
                )}
              </span>
            </div>
          ) : brokerEntryTime ? (
            <div className="text-[11px] font-mono font-medium text-[var(--muted)] mt-0.5 whitespace-nowrap">
              {brokerEntryTime} Broker
            </div>
          ) : null}
        </div>
        <span aria-label={state || undefined} className={`text-[10px] font-mono font-black tracking-wide px-2.5 py-1 rounded-md border ${
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
    </Wrapper>
  );
}

function ChartLine(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}>
      <path d="M3 3v18h18" />
      <path d="m19 9-5 5-4-4-3 3" />
    </svg>
  );
}
