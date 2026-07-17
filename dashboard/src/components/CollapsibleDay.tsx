"use client";

import { useState } from "react";
import { SignalCard } from "./SignalCard";
import type { Signal } from "@/lib/types";
import { useLocale } from "./LocaleProvider";

function weekdayLabel(dateStr: string, locale: "VN" | "EN"): string {
  const [year, month, dayOfMonth] = dateStr.split("-").map(Number);
  const day = new Date(year, month - 1, dayOfMonth).getDay();
  const labels = locale === "EN"
    ? ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    : ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];
  return labels[day];
}

interface CollapsibleDayProps {
  date: string;
  signals: Signal[];
  isVIP: boolean;
  defaultOpen?: boolean;
}

export function CollapsibleDay({ date, signals, isVIP, defaultOpen = false }: CollapsibleDayProps) {
  const [open, setOpen] = useState(defaultOpen);
  const { locale } = useLocale();
  const daySignals = [...signals].sort((a, b) => b.hour - a.hour);
  const weekday = weekdayLabel(date, locale);
  const verdictCounts = daySignals.reduce(
    (counts, signal) => {
      if (signal.signal === "BUY") counts.buy += 1;
      if (signal.signal === "SELL") counts.sell += 1;
      if (signal.signal === "WAIT") counts.wait += 1;
      return counts;
    },
    { buy: 0, sell: 0, wait: 0 },
  );

  return (
    <section className="terminal-panel history-day overflow-hidden rounded-xl">
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="history-day-toggle group flex w-full items-center gap-3 px-4 py-3.5 text-left sm:px-5"
      >
        <svg
          className={`h-4 w-4 shrink-0 text-[color:var(--terminal-accent)] transition-transform duration-200 ${open ? "rotate-90" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
        </svg>
        <div className="min-w-0">
          <h2 className="font-mono text-base font-black text-zinc-800 dark:text-zinc-100">
            {date} <span className="text-zinc-400 dark:text-zinc-500">({weekday})</span>
          </h2>
          <p className="mt-0.5 text-[11px] font-semibold text-zinc-500 dark:text-zinc-400">
            {daySignals.length} {locale === "EN" ? `signal${daySignals.length !== 1 ? "s" : ""}` : "tín hiệu"}
          </p>
        </div>
        <div className="ml-auto hidden items-center gap-3 font-mono text-xs font-bold sm:flex">
          <VerdictCount label="BUY" value={verdictCounts.buy} tone="buy" />
          <VerdictCount label="SELL" value={verdictCounts.sell} tone="sell" />
          <VerdictCount label={locale === "EN" ? "WAIT" : "CHỜ"} value={verdictCounts.wait} tone="wait" />
        </div>
        <span className="history-day-state font-mono text-xs">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="history-day-content grid grid-cols-1 gap-3 px-4 pb-4 pt-4 md:grid-cols-2 xl:grid-cols-3">
          {daySignals.map((signal) => (
            <SignalCard
              key={`${signal.date}-${signal.hour}`}
              signal={signal}
              isVIP={isVIP}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function VerdictCount({ label, value, tone }: { label: string; value: number; tone: "buy" | "sell" | "wait" }) {
  const toneClass = {
    buy: "text-emerald-500",
    sell: "text-red-500",
    wait: "text-zinc-500 dark:text-zinc-400",
  }[tone];

  return <span className={toneClass}>{label} {value}</span>;
}
