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
        <span className="font-mono text-xs font-semibold text-zinc-400 dark:text-zinc-500">{pair}</span>
        <svg className="w-3.5 h-3.5 text-zinc-300 dark:text-zinc-600" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
        </svg>
      </div>
    );
  }

  if (pair === "Stock-DIRECTION" || pair === "GBP-DIRECTION") {
    const isBuy = direction === "BUY";
    const isGBP = pair === "GBP-DIRECTION";
    const borderColor = isGBP ? "border-purple-300/60 dark:border-purple-400/30" : "border-cyan-300/60 dark:border-cyan-400/30";
    const bgColor = isGBP ? "bg-purple-50/80 dark:bg-purple-400/10" : "bg-cyan-50/80 dark:bg-cyan-400/10";
    const shadowColor = isGBP ? "shadow-[0_0_26px_rgba(168,85,247,0.18)]" : "shadow-[0_0_26px_rgba(34,211,238,0.18)]";
    const textColor = isGBP ? "text-purple-700 dark:text-purple-200" : "text-cyan-700 dark:text-cyan-200";
    const iconBg = isGBP ? "bg-purple-500/15 text-purple-500 shadow-[0_0_14px_rgba(168,85,247,0.45)]" : "bg-cyan-500/15 text-cyan-500 shadow-[0_0_14px_rgba(34,211,238,0.45)]";
    return (
      <div className={`my-2 flex items-center justify-between gap-2 rounded-2xl border ${borderColor} ${bgColor} px-3 py-2 ${shadowColor}`}>
        <span className={`inline-flex items-center gap-2 font-mono text-[11px] font-black tracking-wide ${textColor}`}>
          <span className={`grid h-5 w-5 place-items-center rounded-lg ${iconBg}`}>
            <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" aria-hidden="true">
              <path d="M7 7h10v10M17 7 7 17" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </span>
          {pair}
        </span>
        <span className={`text-[10px] font-black tracking-wide px-2.5 py-1 rounded-xl border ${
          isBuy
            ? "border-emerald-300/70 bg-emerald-500/15 text-emerald-600 dark:text-emerald-300"
            : "border-red-300/70 bg-red-500/15 text-red-600 dark:text-red-300"
        }`}>
          {getSignalLabel(direction, locale)}
        </span>
      </div>
    );
  }

  if (!direction || direction === "-" || direction === "--") {
    return (
      <div className="flex items-center justify-between py-1.5">
        <span className="font-mono text-xs font-semibold text-zinc-400 dark:text-zinc-500">{pair}</span>
        <span className="text-xs text-zinc-300 dark:text-zinc-600 font-mono">{direction === "--" ? "--" : "—"}</span>
      </div>
    );
  }

  const isBuy = direction === "BUY";

  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="font-mono text-sm font-black text-zinc-800 dark:text-zinc-100">{pair}</span>
      <span className={`text-[10px] font-black tracking-wide px-2.5 py-1 rounded-xl ${isBuy ? "bg-emerald-500/12 text-emerald-600 dark:text-emerald-300" : "bg-red-500/12 text-red-600 dark:text-red-300"}`}>
        {getSignalLabel(direction, locale)}
      </span>
    </div>
  );
}
