"use client";

import { CollapsibleDay } from "./CollapsibleDay";
import type { Signal } from "@/lib/types";

interface HistoryListProps {
  signals: Signal[];
  isVIP: boolean;
}

export function HistoryList({ signals, isVIP }: HistoryListProps) {
  const dateMap = new Map<string, Signal[]>();
  for (const s of signals) {
    if (!dateMap.has(s.date)) dateMap.set(s.date, []);
    dateMap.get(s.date)!.push(s);
  }
  const dates = [...dateMap.keys()].sort().reverse().slice(0, 7);

  if (dates.length === 0) {
    return (
      <div className="text-center py-12 text-zinc-400 dark:text-zinc-500 text-base">
        Chưa có signal nào
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {dates.map((date, i) => (
        <CollapsibleDay
          key={date}
          date={date}
          signals={dateMap.get(date) || []}
          isVIP={isVIP}
          defaultOpen={i === 0}
        />
      ))}
    </div>
  );
}
