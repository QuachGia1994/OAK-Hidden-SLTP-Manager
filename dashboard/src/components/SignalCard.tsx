import {
  getSignalColor,
  getSignalLabel,
  formatHour,
  brokerToLocalTime,
  getHourNote,
  weekdayFromDate,
  getFocusGbpPairs,
  signalHasThuNoGoldLabel,
  signalXauNoTradeTag,
} from "@/lib/constants";
import { PairBadge } from "./PairBadge";
import type { Signal } from "@/lib/types";

function isD1MatchNote(note: string | null | undefined) {
  return !!note && note.includes("tick match D1");
}

function getD1MatchNote(direction: Signal["d_direction"]) {
  if (direction === "BUY") return "XAUUSD: Mua BUY (tick match D1)";
  if (direction === "SELL") return "XAUUSD: Bán SELL (tick match D1)";
  return "XAUUSD: tick match D1";
}

/** Strip long T5-no-gold prose; keep pair-rule note only (badge handles the label). */
function stripThuNoGoldProse(note: string | null | undefined): string | null {
  if (!note) return null;
  let s = note
    .replace(/\s*[·•|]\s*⚠?\s*Thứ\s*5:[^·\n]*/gi, "")
    .replace(/\s*⚠\s*Thứ\s*5:[^\n]*/gi, "")
    .replace(/\s*[·•|]\s*⚠?\s*Thursday:[^·\n]*/gi, "")
    .replace(/\s*⚠\s*Thursday:[^\n]*/gi, "")
    .replace(/\s*KHÔNG\s*đánh\s*Vàng[^\n·|]*/gi, "")
    .replace(/\s*NO\s*Gold[^\n·|]*/gi, "")
    .replace(/\s*[·•|]\s*$/g, "")
    .replace(/^\s*[·•|]\s*/g, "")
    .trim();
  return s || null;
}

export function SignalCard({ signal, isVIP, showD1Match = false }: { signal: Signal; isVIP?: boolean; showD1Match?: boolean }) {
  const isMissed = signal.missed;
  const localTime = brokerToLocalTime(signal.hour, 45);
  const weekday = weekdayFromDate(signal.date);
  const fallbackHourNote = isD1MatchNote(signal.hour_note) ? getHourNote(signal.hour, weekday) : signal.hour_note;
  const rawHourNote = showD1Match ? getD1MatchNote(signal.d_direction) : (fallbackHourNote || getHourNote(signal.hour, weekday));
  const noGoldEntry = signalHasThuNoGoldLabel(signal.hour, signal.date, signal.hour_note);
  const noGoldTag = signalXauNoTradeTag(signal.hour, signal.date) || "no-trade";
  // Only keep short pair/rule note; no-gold lives solely on XAU badge
  const hourNote = showD1Match ? rawHourNote : stripThuNoGoldProse(rawHourNote);

  const focusGbp = getFocusGbpPairs(signal.hour);
  const xauDir =
    signal.pair_dirs?.XAUUSD ||
    (signal.signal === "BUY" || signal.signal === "SELL" ? signal.signal : "-");

  const xauBadgeDir = !isVIP
    ? "locked"
    : noGoldEntry
      ? xauDir === "BUY" || xauDir === "SELL"
        ? `no_gold_thu:${xauDir}:${noGoldTag}`
        : `no_gold_thu:${noGoldTag}`
      : xauDir || "-";

  return (
    <div className="group border border-zinc-200/80 dark:border-zinc-800 rounded-xl bg-white/90 dark:bg-zinc-900/55 overflow-hidden shadow-sm hover:shadow-md transition-all duration-200">
      {/* Header */}
      <div className="px-3 py-2 border-b border-zinc-100 dark:border-zinc-800/80 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <span className="font-mono text-base font-semibold tabular-nums text-zinc-900 dark:text-zinc-100">
            {localTime}
          </span>
          <span className="text-[11px] text-zinc-400 dark:text-zinc-500 font-mono">
            ({formatHour(signal.hour)}:45 Brk)
          </span>
          {isMissed && (
            <span className="text-[9px] font-medium tracking-wide uppercase px-1.5 py-0.5 rounded bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-500/20">
              BỎ LỠ
            </span>
          )}
        </div>
        <span className="text-[11px] text-zinc-400 dark:text-zinc-500 font-mono shrink-0">{signal.date}</span>
      </div>

      {/* Conclusion — pattern signal only */}
      <div className="px-3 py-2.5">
        <div className="text-[9px] uppercase tracking-widest text-zinc-400 dark:text-zinc-500 mb-1 font-medium">KẾT LUẬN</div>
        {isVIP ? (
          <span className={`text-2xl sm:text-3xl font-bold font-mono leading-none ${getSignalColor(signal.signal)}`}>
            {getSignalLabel(signal.signal)}
          </span>
        ) : (
          <div className="flex items-center justify-between gap-2 rounded-md border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-900/50 px-2.5 py-2">
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold text-zinc-300 dark:text-zinc-600">🔒</span>
              <div>
                <div className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">VIP Only</div>
                <div className="text-[9px] uppercase tracking-wider text-zinc-400 dark:text-zinc-500">Unlock to view</div>
              </div>
            </div>
            <span className="text-[9px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded bg-zinc-200/70 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
              Locked
            </span>
          </div>
        )}
      </div>

      {/* XAU badge = sole T5 no-gold label; GBP focus below */}
      <div className="px-3 py-1.5 border-t border-zinc-100 dark:border-zinc-800/60 space-y-0">
        <PairBadge pair="XAUUSD" direction={xauBadgeDir} />
        {focusGbp.length > 0 && (
          <div className="pt-1 pb-0.5">
            <div className="text-[9px] uppercase tracking-widest text-zinc-400 dark:text-zinc-500 font-medium mb-0.5">
              Cặp GBP tập trung
            </div>
            {focusGbp.map((pair) => (
              <PairBadge
                key={pair}
                pair={pair}
                direction={isVIP ? "focus" : "locked"}
                focusOnly={isVIP}
              />
            ))}
          </div>
        )}
        {focusGbp.length === 0 && isVIP && !noGoldEntry && (
          <div className="pt-1 text-[11px] text-zinc-400 dark:text-zinc-500">Không có mốc GBP — chỉ Vàng</div>
        )}
      </div>

      {/* Hour Note — pair rules only (no long no-gold prose) */}
      {hourNote && (
        <div className="px-3 py-1.5 border-t border-zinc-100 dark:border-zinc-800/60 bg-zinc-50/90 dark:bg-zinc-900/40">
          {showD1Match ? (
            <div className="flex items-center gap-1.5">
              <svg className="w-3 h-3 text-emerald-500 dark:text-emerald-400 shrink-0" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium leading-snug">{hourNote}</p>
            </div>
          ) : (
            <p className="text-[11px] text-zinc-500 dark:text-zinc-400 leading-snug">{hourNote}</p>
          )}
        </div>
      )}
    </div>
  );
}
