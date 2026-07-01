import { getSignalColor, getSignalLabel, formatHour, brokerToLocalTime, ALL_PAIRS, HOUR_NOTES } from "@/lib/constants";
import { PairBadge } from "./PairBadge";
import type { Signal } from "@/lib/types";

function entryTimeToLocal(entryTime: string): string {
  const match = entryTime.match(/^(\d{1,2}):(\d{2})$/);
  if (!match) return entryTime;
  const h = parseInt(match[1]);
  const m = parseInt(match[2]);
  return brokerToLocalTime(h, m);
}

function EntryTimeDisplay({ entry_time }: { entry_time: Signal["entry_time"] }) {
  if (!entry_time) return null;

  // Dict: per-pair entry times (H=16)
  if (typeof entry_time === "object") {
    const xau = entry_time["XAUUSD"];
    const gbp = entry_time["GBPUSD"]; // representative of GBP group
    if (!xau && !gbp) return null;
    return (
      <div className="text-right pb-0.5">
        <div className="text-[10px] uppercase tracking-wider text-zinc-400 dark:text-zinc-500 mb-0.5">VÀO LỆNH</div>
        {xau && (
          <div className="font-mono text-sm text-zinc-800 dark:text-zinc-200">
            XAUUSD: <span className="font-semibold">{entryTimeToLocal(xau)}</span>
          </div>
        )}
        {gbp && (
          <div className="font-mono text-sm text-zinc-800 dark:text-zinc-200">
            Nhóm GBP: <span className="font-semibold">{entryTimeToLocal(gbp)}</span>
          </div>
        )}
      </div>
    );
  }

  // String: single entry time
  const localEntryTime = entryTimeToLocal(entry_time);
  return (
    <div className="text-right pb-0.5">
      <div className="text-[10px] uppercase tracking-wider text-zinc-400 dark:text-zinc-500 mb-0.5">VÀO LỆNH</div>
      <div className="font-mono text-lg font-semibold text-zinc-800 dark:text-zinc-200">{localEntryTime}</div>
    </div>
  );
}

export function SignalCard({ signal, prevSignal }: { signal: Signal; prevSignal?: Signal | null }) {
  const isMissed = signal.missed;
  const localTime = brokerToLocalTime(signal.hour, 45);

  return (
    <div className="group border border-zinc-200 dark:border-zinc-800 rounded-xl bg-white dark:bg-zinc-900/50 overflow-hidden shadow-sm hover:shadow-md transition-shadow duration-200">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-zinc-100 dark:border-zinc-800/80 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="font-mono text-lg font-semibold text-zinc-900 dark:text-zinc-100">
            {localTime}
          </span>
          <span className="text-xs text-zinc-400 dark:text-zinc-500 font-mono">
            ({formatHour(signal.hour)}:45 Broker)
          </span>
          {isMissed && (
            <span className="text-[10px] font-medium tracking-wide uppercase px-2 py-0.5 rounded-full bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-500/20">
              BỎ LỠ
            </span>
          )}
        </div>
        <span className="text-xs text-zinc-400 dark:text-zinc-500 font-mono">{signal.date}</span>
      </div>

      {/* Conclusion */}
      <div className="px-5 py-5">
        <div className="text-[10px] uppercase tracking-widest text-zinc-400 dark:text-zinc-500 mb-2 font-medium">KẾT LUẬN</div>
        <div className="flex items-end gap-4">
          <span className={`text-4xl font-bold font-mono leading-none ${getSignalColor(signal.signal)}`}>
            {getSignalLabel(signal.signal)}
          </span>
          <EntryTimeDisplay entry_time={signal.entry_time} />
        </div>
      </div>

      {/* Pair Directions */}
      <div className="px-5 py-3 border-t border-zinc-100 dark:border-zinc-800/60 space-y-0.5">
        {ALL_PAIRS.map((pair) => (
          <PairBadge
            key={pair}
            pair={pair}
            direction={signal.pair_dirs?.[pair] || "-"}
          />
        ))}
      </div>

      {/* Hour Note */}
      {HOUR_NOTES[signal.hour] && (
        <div className="px-5 py-2.5 border-t border-zinc-100 dark:border-zinc-800/60 bg-zinc-50 dark:bg-zinc-900/40">
          <p className="text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">{HOUR_NOTES[signal.hour]}</p>
        </div>
      )}
    </div>
  );
}
