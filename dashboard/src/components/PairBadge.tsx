"use client";

import { getSignalLabel } from "@/lib/constants";
import { useLocale } from "./LocaleProvider";

interface PairBadgeProps {
  pair: string;
  direction: string;
  /** GBP focus mode: show pair as active without Mua/Bán */
  focusOnly?: boolean;
}

export function PairBadge({ pair, direction, focusOnly = false }: PairBadgeProps) {
  const { locale } = useLocale();
  if (direction === "locked") {
    return (
      <div className="flex items-center justify-between py-1">
        <span className="font-mono text-xs text-zinc-400 dark:text-zinc-500">{pair}</span>
        <svg className="w-3.5 h-3.5 text-zinc-300 dark:text-zinc-600" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z" />
        </svg>
      </div>
    );
  }

  if (focusOnly) {
    return (
      <div className="flex items-center justify-between py-1">
        <span className="font-mono text-xs font-medium text-zinc-800 dark:text-zinc-200">{pair}</span>
        <span className="text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded bg-sky-50 dark:bg-sky-500/10 text-sky-700 dark:text-sky-300 border border-sky-200/70 dark:border-sky-500/20">
          {locale === "EN" ? "Focus" : "Focus"}
        </span>
      </div>
    );
  }

  if (pair === "D-DIRECTION") {
    const isBuy = direction === "BUY";
    return (
      <div className="my-1 flex items-center justify-between gap-2 rounded-lg border border-cyan-300/60 dark:border-cyan-400/30 bg-cyan-50/80 dark:bg-cyan-400/10 px-2 py-1.5 shadow-[0_0_22px_rgba(34,211,238,0.16)]">
        <span className="inline-flex items-center gap-1.5 font-mono text-[11px] font-bold tracking-wide text-cyan-700 dark:text-cyan-200">
          <span className="h-1.5 w-1.5 rounded-full bg-cyan-500 dark:bg-cyan-300 shadow-[0_0_10px_rgba(34,211,238,0.9)]" />
          D-DIRECTION
        </span>
        <span className={`text-[10px] font-black tracking-wide px-2 py-0.5 rounded border ${
          isBuy
            ? "border-emerald-300/70 bg-emerald-500/15 text-emerald-600 dark:text-emerald-300"
            : "border-red-300/70 bg-red-500/15 text-red-600 dark:text-red-300"
        }`}>
          {getSignalLabel(direction, locale)}
        </span>
      </div>
    );
  }

  // No-trade gold badge: "no_gold_thu:BUY:H=3-4" or "no_gold_thu:SELL:T6 H=3-11" or "no_gold_thu"
  if (direction === "no_gold_thu" || direction?.startsWith("no_gold_thu:")) {
    const parts = direction.split(":");
    // ["no_gold_thu"] | ["no_gold_thu", "BUY"] | ["no_gold_thu", "BUY", "H=3-4"]
    const computed = parts.length >= 2 && (parts[1] === "BUY" || parts[1] === "SELL") ? parts[1] : "";
    const tag =
      parts.length >= 3
        ? parts.slice(2).join(":")
        : parts.length === 2 && parts[1] !== "BUY" && parts[1] !== "SELL"
          ? parts[1]
          : "no-trade";
    const label =
      locale === "EN"
        ? `No trade${computed ? ` ${computed === "BUY" ? "Buy" : "Sell"}` : ""} · ${tag || "no-trade"}`
        : `Không đánh${computed ? ` ${computed === "BUY" ? "Mua" : "Bán"}` : ""} · ${tag || "no-trade"}`;
    return (
      <div className="flex items-center justify-between py-1 gap-2">
        <span className="font-mono text-xs font-semibold text-zinc-800 dark:text-zinc-100">{pair}</span>
        <span className="text-[10px] font-bold tracking-wide px-2 py-0.5 rounded bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-400/50 dark:border-amber-500/40 shadow-sm">
          {label}
        </span>
      </div>
    );
  }

  if (!direction || direction === "-" || direction === "--") {
    return (
      <div className="flex items-center justify-between py-1">
        <span className="font-mono text-xs text-zinc-400 dark:text-zinc-500">{pair}</span>
        <span className="text-xs text-zinc-300 dark:text-zinc-600 font-mono">{direction === "--" ? "--" : "—"}</span>
      </div>
    );
  }

  const isBuy = direction === "BUY";

  return (
    <div className="flex items-center justify-between py-1">
      <span className="font-mono text-xs font-medium text-zinc-700 dark:text-zinc-300">{pair}</span>
      <span className={`text-[10px] font-semibold tracking-wide px-2 py-0.5 rounded ${isBuy ? "bg-emerald-50 dark:bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-red-50 dark:bg-red-500/10 text-red-600 dark:text-red-400"}`}>
        {getSignalLabel(direction, locale)}
      </span>
    </div>
  );
}
