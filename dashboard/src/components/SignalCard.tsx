"use client";

import {
  getSignalColor,
  getSignalLabel,
  getRhythmLabel,
  formatHour,
  getHourNote,
  weekdayFromDate,
} from "@/lib/constants";
import { PairBadge } from "./PairBadge";
import type { Signal } from "@/lib/types";
import { useLocale } from "./LocaleProvider";
import { BrokerLocalTime } from "./BrokerLocalTime";

function translateHourNote(note: string | null | undefined, locale: "VN" | "EN"): string | null {
  if (!note) return null;
  if (locale === "VN") return note;
  const map: Array<[RegExp, string]> = [
    [/Đảo signal ra Vàng \(XAUUSD\)/g, "Reverse to gold (XAUUSD)"],
    [/Chỉ Vàng \(XAUUSD\)/g, "XAU only"],
    [/XAUUSD theo D-direction H=4/g, "XAUUSD follows H=4 D-direction"],
  ];
  return map.reduce((acc, [pattern, replacement]) => acc.replace(pattern, replacement), note);
}

export function SignalCard({
  signal,
  isVIP,
}: {
  signal: Signal;
  isVIP?: boolean;
}) {
  const { locale } = useLocale();
  const weekday = weekdayFromDate(signal.date);
  const fallbackHourNote = signal.date
    ? getHourNote(signal.hour, weekday)
    : signal.hour_note;
  const rawHourNote = fallbackHourNote || getHourNote(signal.hour, weekday);
  const hourNote = translateHourNote(rawHourNote, locale);
  const rhythmLabel = getRhythmLabel(signal.hour, locale);
  const showHourNote = Boolean(
    hourNote &&
      rawHourNote !== "Chỉ Vàng (XAUUSD)" &&
      hourNote !== "XAU only",
  );

  const xauDir =
    signal.pair_dirs?.XAUUSD ||
    (signal.signal === "BUY" || signal.signal === "SELL" ? signal.signal : "-");

  const xauBadgeDir = !isVIP
    ? "locked"
    : xauDir || "-";

  return (
    <div className="group border border-zinc-200/80 dark:border-zinc-800 rounded-xl bg-white/90 dark:bg-zinc-900/55 overflow-hidden shadow-sm hover:shadow-md transition-all duration-200">
      <div className="px-3 py-2 border-b border-zinc-100 dark:border-zinc-800/80 flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <span className="font-mono text-base font-semibold tabular-nums text-zinc-900 dark:text-zinc-100">
            <BrokerLocalTime date={signal.date} hour={signal.hour} />
          </span>
          <span className="text-[11px] text-zinc-400 dark:text-zinc-500 font-mono">
            ({formatHour(signal.hour)}:45 Brk)
          </span>
          {rhythmLabel && (
            <span className="text-[9px] font-medium tracking-wide uppercase px-1.5 py-0.5 rounded bg-amber-50 dark:bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-200 dark:border-amber-500/20">
              {rhythmLabel}
            </span>
          )}
        </div>
        <span className="text-[11px] text-zinc-400 dark:text-zinc-500 font-mono shrink-0">{signal.date}</span>
      </div>

      <div className="px-3 py-2.5">
        <div className="text-[9px] uppercase tracking-widest text-zinc-400 dark:text-zinc-500 mb-1 font-medium">
          {locale === "EN" ? "Verdict" : "Kết luận"}
        </div>
        {isVIP ? (
          <span className={`text-2xl sm:text-3xl font-bold font-mono leading-none ${getSignalColor(signal.signal)}`}>
            {getSignalLabel(signal.signal, locale)}
          </span>
        ) : (
          <div className="flex items-center justify-between gap-2 rounded-md border border-dashed border-zinc-200 dark:border-zinc-800 bg-zinc-50/80 dark:bg-zinc-900/50 px-2.5 py-2">
            <div className="flex items-center gap-2">
              <span className="text-lg font-bold text-zinc-300 dark:text-zinc-600">🔒</span>
              <div>
                <div className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
                  {locale === "EN" ? "VIP only" : "Chỉ VIP"}
                </div>
                <div className="text-[9px] uppercase tracking-wider text-zinc-400 dark:text-zinc-500">
                  {locale === "EN" ? "Unlock to view" : "Mở khóa để xem"}
                </div>
              </div>
            </div>
            <span className="text-[9px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded bg-zinc-200/70 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
              {locale === "EN" ? "Locked" : "Khóa"}
            </span>
          </div>
        )}
      </div>

      <div className="px-3 py-1.5 border-t border-zinc-100 dark:border-zinc-800/60 space-y-0">
        <PairBadge pair="XAUUSD" direction={xauBadgeDir} />
        {signal.pair_dirs?.["D-DIRECTION"] && (
          <PairBadge
            pair="D-DIRECTION"
            direction={isVIP ? signal.pair_dirs["D-DIRECTION"] : "locked"}
          />
        )}
        {isVIP && (
          <div className="pt-1 text-[11px] text-zinc-400 dark:text-zinc-500">
            {locale === "EN" ? "XAU only" : "Chỉ Vàng (XAUUSD)"}
          </div>
        )}
      </div>

      {showHourNote && (
        <div className="px-3 py-1.5 border-t border-zinc-100 dark:border-zinc-800/60 bg-zinc-50/90 dark:bg-zinc-900/40">
          <p className="text-[11px] text-zinc-500 dark:text-zinc-400 leading-snug">{hourNote}</p>
        </div>
      )}
    </div>
  );
}
