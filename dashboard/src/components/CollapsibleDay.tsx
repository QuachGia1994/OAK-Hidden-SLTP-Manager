"use client";

import { useState } from "react";
import { SignalCard } from "./SignalCard";
import type { Signal } from "@/lib/types";

function weekdayLabel(dateStr: string): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  const day = new Date(y, m - 1, d).getDay();
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
  const daySignals = [...signals].sort((a, b) => b.hour - a.hour);
  const weekday = weekdayLabel(date);

  return (
    <div className="rounded-xl border border-zinc-200/80 dark:border-zinc-800 bg-white/70 dark:bg-zinc-900/35 shadow-sm overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-3 w-full text-left group px-4 py-3.5"
      >
        <svg
          className={`w-4 h-4 text-zinc-400 dark:text-zinc-500 transition-transform duration-200 ${open ? "rotate-90" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
        </svg>
        <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 font-mono">
          {date} <span className="text-zinc-400 dark:text-zinc-500">({weekday})</span>
        </h2>
        <span className="text-[10px] text-zinc-400 dark:text-zinc-500 ml-auto">
          {daySignals.length} signal{daySignals.length !== 1 ? "s" : ""}
        </span>
      </button>
      {open && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 px-4 pb-4">
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
