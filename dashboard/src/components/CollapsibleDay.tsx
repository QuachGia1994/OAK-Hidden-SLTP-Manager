"use client";

import { useState } from "react";
import { SignalCard } from "./SignalCard";
import type { Signal } from "@/lib/types";
import { useLocale } from "./LocaleProvider";

function weekdayLabel(dateStr: string): string {
  const [year, month, dayOfMonth] = dateStr.split("-").map(Number);
  const day = new Date(year, month - 1, dayOfMonth).getDay();
  const labels = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];
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
  const weekday = weekdayLabel(date);

  return (
    <div className="glass-card overflow-hidden rounded-[1.35rem]">
      <button
        onClick={() => setOpen(!open)}
        className="group flex w-full items-center gap-3 px-4 py-4 text-left sm:px-5"
      >
        <svg
          className={`h-4 w-4 text-emerald-500 transition-transform duration-200 ${open ? "rotate-90" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
        </svg>
        <h2 className="font-mono text-base font-black text-zinc-800 dark:text-zinc-100">
          {date} <span className="text-zinc-400 dark:text-zinc-500">({weekday})</span>
        </h2>
        <span className="ml-auto rounded-full border border-zinc-200/70 bg-zinc-900/[0.035] px-3 py-1 text-[10px] font-bold uppercase tracking-[0.12em] text-zinc-500 dark:border-white/10 dark:bg-white/[0.05] dark:text-zinc-400">
          {daySignals.length} {locale === "EN" ? `signal${daySignals.length !== 1 ? "s" : ""}` : "tín hiệu"}
        </span>
      </button>
      {open && (
        <div className="grid grid-cols-1 gap-3 border-t border-zinc-200/55 px-4 pb-4 pt-4 dark:border-white/10 md:grid-cols-2 xl:grid-cols-3">
          {daySignals.map((signal) => (
            <SignalCard
              key={`${signal.date}-${signal.hour}`}
              signal={signal}
              isVIP={isVIP}
            />
          ))}
        </div>
      )}
    </div>
  );
}
