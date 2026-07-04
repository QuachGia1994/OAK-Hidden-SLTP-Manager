import { getSignalColor, getSignalLabel, formatHour, brokerToLocalTime, GBP_PAIRS, getHourNote, weekdayFromDate } from "@/lib/constants";
import { PairBadge } from "./PairBadge";
import type { Signal } from "@/lib/types";

function getD1MatchNote(direction: Signal["d_direction"]) {
  if (direction === "BUY") return "XAUUSD: Mua BUY (tick match D1)";
  if (direction === "SELL") return "XAUUSD: Bán SELL (tick match D1)";
  return "XAUUSD: tick match D1";
}

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

export function SignalCard({ signal, isVIP, showD1Match = false }: { signal: Signal; isVIP?: boolean; showD1Match?: boolean }) {
  const isMissed = signal.missed;
  const localTime = brokerToLocalTime(signal.hour, 45);
  const weekday = weekdayFromDate(signal.date);
  const hourNote = showD1Match ? getD1MatchNote(signal.d_direction) : (signal.hour_note || getHourNote(signal.hour, weekday));

  return (
    <div className="group border border-zinc-200/80 dark:border-zinc-800 rounded-xl bg-white/90 dark:bg-zinc-900/55 overflow-hidden shadow-sm hover:shadow-md transition-all duration-200">
      {/* Header */}
      <div className="px-5 py-3.5 border-b border-zinc-100 dark:border-zinc-800/80 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <span className="font-mono text-lg font-semibold tabular-nums text-zinc-900 dark:text-zinc-100">
            {localTime}
          </span>
          <span className="text-xs text-zinc-400 dark:text-zinc-500 font-mono">
            ({formatHour(signal.hour)}:45 Broker)
          </span>
          {isMissed && (
            <span className="text-[10px] font-medium tracking-wide uppercase px-2 py-0.5 rounded-md bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-500/20">
              BỎ LỠ
            </span>
          )}
        </div>
        <span className="text-xs text-zinc-400 dark:text-zinc-500 font-mono">{signal.date}</span>
      </div>

      {/* Conclusion */}
      <div className="px-5 py-5">
        <div className="text-[10px] uppercase tracking-widest text-zinc-400 dark:text-zinc-500 mb-2 font-medium">KẾT LUẬN</div>
        {isVIP ? (
          <div className="flex items-end gap-4">
            <span className={`text-4xl font-bold font-mono leading-none ${getSignalColor(signal.signal)}`}>
              {getSignalLabel(signal.signal)}
            </span>
            <EntryTimeDisplay entry_time={signal.entry_time} />
          </div>
        ) : (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-900/50 px-4 py-3">
            <div className="flex items-center gap-3">
              <span className="text-2xl font-bold text-zinc-300 dark:text-zinc-600">🔒</span>
              <div>
                <div className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">VIP Only</div>
                <div className="text-[10px] uppercase tracking-wider text-zinc-400 dark:text-zinc-500">Unlock details with access</div>
              </div>
            </div>
            <span className="text-[10px] font-semibold uppercase tracking-wide px-2.5 py-1 rounded-md bg-zinc-200/70 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
              Locked
            </span>
          </div>
        )}
      </div>

      {/* All Pairs - flat list */}
      <div className="px-5 py-3 border-t border-zinc-100 dark:border-zinc-800/60 space-y-0.5">
        {["XAUUSD", ...GBP_PAIRS].map((pair) => (
          <PairBadge
            key={pair}
            pair={pair}
            direction={isVIP ? (signal.pair_dirs?.[pair] || "-") : "locked"}
          />
        ))}
      </div>

      {/* Hour Note */}
      {hourNote && (
        <div className="px-5 py-2.5 border-t border-zinc-100 dark:border-zinc-800/60 bg-zinc-50/90 dark:bg-zinc-900/40">
          {showD1Match ? (
            <div className="flex items-center gap-1.5">
              <svg className="w-3.5 h-3.5 text-emerald-500 dark:text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-xs text-emerald-600 dark:text-emerald-400 font-medium leading-relaxed">{hourNote}</p>
            </div>
          ) : (
            <p className="text-xs text-zinc-500 dark:text-zinc-400 leading-relaxed">{hourNote}</p>
          )}
        </div>
      )}
    </div>
  );
}
