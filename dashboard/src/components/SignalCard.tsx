import { getSignalColor, getSignalLabel, formatHour, brokerToLocalTime, brokerToLocalHour, ALL_PAIRS } from "@/lib/constants";
import { PairBadge } from "./PairBadge";
import type { Signal } from "@/lib/types";

function entryTimeToLocal(entryTime: string): string {
  const match = entryTime.match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return entryTime;
  const h = parseInt(match[1]);
  const m = parseInt(match[2]);
  return brokerToLocalTime(h, m);
}

export function SignalCard({ signal, prevSignal }: { signal: Signal; prevSignal?: Signal | null }) {
  const isMissed = signal.missed;
  const localTime = brokerToLocalTime(signal.hour, 45);
  const localEntryTime = signal.entry_time ? entryTimeToLocal(signal.entry_time) : null;

  return (
    <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg bg-white dark:bg-zinc-900/50 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-zinc-100 dark:border-zinc-800 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="font-mono text-base text-zinc-900 dark:text-zinc-200">
            {localTime}
          </span>
          <span className="text-xs text-zinc-400 dark:text-zinc-500 font-mono">
            ({formatHour(signal.hour)}:45 Broker)
          </span>
          {isMissed && (
            <span className="text-xs font-mono px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-500 dark:text-zinc-500">
              BỎ LỠ
            </span>
          )}
        </div>
        <span className="text-xs text-zinc-400 dark:text-zinc-500 font-mono">{signal.date}</span>
      </div>

      {/* Conclusion */}
      <div className="px-4 py-4">
        <div className="text-xs uppercase tracking-wider text-zinc-500 dark:text-zinc-400 mb-1">KẾT LUẬN</div>
        <div className="flex items-center gap-3">
          <span className={`text-3xl font-bold font-mono ${getSignalColor(signal.signal)}`}>
            {getSignalLabel(signal.signal)}
          </span>
          {localEntryTime && (
            <div className="text-right">
              <div className="text-xs text-zinc-500 dark:text-zinc-400">VÀO LỆNH</div>
              <div className="font-mono text-base text-zinc-900 dark:text-zinc-200">{localEntryTime}</div>
            </div>
          )}
        </div>
      </div>

      {/* Pair Directions */}
      <div className="px-4 py-3 border-t border-zinc-100 dark:border-zinc-800/50">
        {ALL_PAIRS.map((pair) => (
          <PairBadge
            key={pair}
            pair={pair}
            direction={signal.pair_dirs?.[pair] || "-"}
            entryPrice={signal.entry_prices?.[pair] ?? null}
            currentPrice={signal.current_prices?.[pair] ?? null}
            prevDirection={prevSignal?.pair_dirs?.[pair] ?? null}
          />
        ))}
      </div>

      {/* Hour Note */}
      {signal.hour_note && (
        <div className="px-4 py-2 border-t border-zinc-100 dark:border-zinc-800/50 bg-zinc-50 dark:bg-zinc-900/30">
          <p className="text-xs text-zinc-500 dark:text-zinc-400">{signal.hour_note}</p>
        </div>
      )}
    </div>
  );
}
