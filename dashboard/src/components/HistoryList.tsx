"use client";

import { CollapsibleDay } from "./CollapsibleDay";
import type { Signal } from "@/lib/types";
import { useLocale } from "./LocaleProvider";

interface HistoryListProps {
  signals: Signal[];
  isVIP: boolean;
}

export function HistoryList({ signals, isVIP }: HistoryListProps) {
  const { locale } = useLocale();
  const dateMap = new Map<string, Signal[]>();
  for (const signal of signals) {
    if (!dateMap.has(signal.date)) dateMap.set(signal.date, []);
    dateMap.get(signal.date)!.push(signal);
  }
  const dates = [...dateMap.keys()].sort().reverse().slice(0, 7);

  if (dates.length === 0) {
    return (
      <div className="glass-card rounded-[1.35rem] px-5 py-12 text-center">
        <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-2xl border border-emerald-400/25 bg-emerald-500/10 text-emerald-500">
          <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" aria-hidden="true">
            <path d="M5 12h14M12 5v14" stroke="currentColor" strokeWidth={2} strokeLinecap="round" />
          </svg>
        </div>
        <p className="text-base font-semibold text-zinc-500 dark:text-zinc-400">
          {locale === "EN" ? "No signals yet" : "Chưa có tín hiệu nào"}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {dates.map((date, index) => (
        <CollapsibleDay
          key={date}
          date={date}
          signals={dateMap.get(date) || []}
          isVIP={isVIP}
          defaultOpen={index === 0}
        />
      ))}
    </div>
  );
}
