"use client";

import {
  formatHour,
  getHourNote,
  getSignalColor,
  getSignalLabel,
  weekdayFromDate,
} from "@/lib/constants";
import type { Signal } from "@/lib/types";
import { BrokerLocalTime } from "./BrokerLocalTime";
import { useLocale } from "./LocaleProvider";
import { PairBadge } from "./PairBadge";

function translateHourNote(note: string | null | undefined, locale: "VN" | "EN"): string | null {
  if (!note) return null;
  if (locale === "VN") return note;
  const map: Array<[RegExp, string]> = [
    [/Đảo signal ra Vàng \(XAUUSD\)/g, "Reverse to gold (XAUUSD)"],
    [/Chỉ Vàng \(XAUUSD\)/g, "XAU only"],
    [/XAUUSD theo D-direction H=4/g, "XAUUSD follows H=4 Stock-direction"],
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
  const fallbackHourNote = signal.date ? getHourNote(signal.hour, weekday) : signal.hour_note;
  const rawHourNote = fallbackHourNote || getHourNote(signal.hour, weekday);
  const hourNote = translateHourNote(rawHourNote, locale);
  const showHourNote = Boolean(
    hourNote &&
      rawHourNote !== "Chỉ Vàng (XAUUSD)" &&
      hourNote !== "XAU only" &&
      signal.hour !== 2 &&
      signal.hour !== 7,
  );

  const xauDir =
    signal.pair_dirs?.XAUUSD ||
    (signal.signal === "BUY" || signal.signal === "SELL" ? signal.signal : "-");
  const xauBadgeDir = !isVIP ? "locked" : xauDir || "-";
  const isSell = signal.signal === "SELL";
  const isBuy = signal.signal === "BUY";

  return (
    <article className="glass-card group signal-rail overflow-hidden rounded-[1.35rem] transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_22px_70px_rgba(0,0,0,0.18)] dark:hover:shadow-[0_26px_80px_rgba(0,0,0,0.45)]">
      <div className="relative px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="font-mono text-2xl font-black tabular-nums text-zinc-950 dark:text-white">
                <BrokerLocalTime date={signal.date} hour={signal.hour} />
              </span>
              <span className="font-mono text-xs text-zinc-400">
                ({formatHour(signal.hour)}:45 Brk)
              </span>
            </div>
          </div>
          <span className="font-mono text-xs text-zinc-400">{signal.date}</span>
        </div>
      </div>

      <div className="border-y border-zinc-200/55 px-4 py-4 dark:border-white/10">
        <div className="mb-1 text-[10px] font-black uppercase tracking-[0.22em] text-zinc-400">
          {locale === "EN" ? "Verdict" : "Kết luận"}
        </div>
        {isVIP ? (
          <span className={`font-mono text-4xl font-black leading-none ${getSignalColor(signal.signal)}`}>
            {getSignalLabel(signal.signal, locale)}
          </span>
        ) : (
          <LockedVerdict locale={locale} />
        )}
      </div>

      <div className={`px-4 py-3 ${isBuy ? "bg-emerald-500/[0.035]" : isSell ? "bg-red-500/[0.035]" : ""}`}>
        <PairBadge pair="XAUUSD" direction={xauBadgeDir} />
        {signal.pair_dirs?.["Stock-DIRECTION"] && (
          <PairBadge
            pair="Stock-DIRECTION"
            direction={isVIP ? signal.pair_dirs["Stock-DIRECTION"] : "locked"}
          />
        )}
        {signal.pair_dirs?.["GBP-DIRECTION"] && (
          <PairBadge
            pair="GBP-DIRECTION"
            direction={isVIP ? signal.pair_dirs["GBP-DIRECTION"] : "locked"}
          />
        )}
      </div>

      {showHourNote && (
        <div className="border-t border-zinc-200/55 bg-amber-500/[0.045] px-4 py-2.5 dark:border-white/10">
          <p className="text-xs leading-relaxed text-zinc-600 dark:text-zinc-300">{hourNote}</p>
        </div>
      )}
    </article>
  );
}

function LockedVerdict({ locale }: { locale: "VN" | "EN" }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-dashed border-zinc-300/70 bg-zinc-500/[0.06] px-3 py-3 dark:border-white/10">
      <div className="flex items-center gap-3">
        <span className="text-xl" aria-hidden="true">🔒</span>
        <div>
          <div className="text-sm font-black text-zinc-800 dark:text-zinc-100">
            {locale === "EN" ? "VIP only" : "Chỉ VIP"}
          </div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-zinc-400">
            {locale === "EN" ? "Unlock to view" : "Mở khóa để xem"}
          </div>
        </div>
      </div>
      <span className="rounded-lg bg-zinc-900/8 px-2 py-1 text-[10px] font-black uppercase text-zinc-500 dark:bg-white/10">
        {locale === "EN" ? "Locked" : "Khóa"}
      </span>
    </div>
  );
}
