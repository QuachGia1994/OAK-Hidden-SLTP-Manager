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
      <div className="text-center py-12 text-zinc-400 dark:text-zinc-500 text-base">
        {locale === "EN" ? "No signals yet" : "Chưa có tín hiệu nào"}
      </div>
    );
  }

  return (
    <div className="space-y-8">
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
