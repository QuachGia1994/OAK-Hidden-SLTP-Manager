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
    [/H=(3|7): Đảo chiều từ H=2\./g, "H=$1: reverse the final H=2 direction."],
    [/XAUUSD theo D-direction H=4/g, "XAUUSD follows H=4 Stock-direction"],
    [/XAUUSD đảo từ H=5 hôm qua/g, "XAUUSD reverses from H=5 yesterday"],
    [/XAUUSD đảo từ H=5 hôm nay/g, "XAUUSD reverses from H=5 today"],
    [/GBPAUD cùng chiều H=5 hôm qua/g, "GBPAUD follows H=5 yesterday"],
    [/GBP group đảo từ H=5 hôm qua \(Thứ 6 cùng chiều\)/g, "GBP reverses from H=5 yesterday (Fri follows)"],
    [/GBP group cùng chiều H=5 hôm nay \(Thứ 6 đảo\)/g, "GBP follows H=5 today (Fri reverses)"],
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
      hourNote !== "XAU only"
  );

  const defaultPairs = (signal.hour === 9 || signal.hour === 14)
    ? ["GBPAUD", "GBPCAD", "GBPJPY", "GBPUSD"]
    : (signal.hour === 2 || signal.hour === 3)
      ? ["XAUUSD", "GBPAUD"]
      : ["XAUUSD"];

  const activePairs = signal.pair_dirs && Object.keys(signal.pair_dirs).length > 0
    ? Object.keys(signal.pair_dirs).filter((p) => p !== "Stock-DIRECTION" && p !== "GBP-DIRECTION")
    : defaultPairs;

  const getPairDir = (pair: string) => {
    if (!isVIP) return "locked";
    return signal.pair_dirs?.[pair] || (signal.signal === "BUY" || signal.signal === "SELL" ? signal.signal : "-");
  };

  const isSell = signal.signal === "SELL";
  const isBuy = signal.signal === "BUY";

  return (
    <article className="terminal-panel group signal-rail overflow-hidden rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] transition-all duration-200 hover:border-[var(--terminal-accent)]/40">
      <div className="relative px-4 py-3.5 border-b border-[var(--panel-border)] bg-[var(--surface)]">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="font-mono text-2xl font-black tabular-nums text-[var(--foreground)]">
                <BrokerLocalTime date={signal.date} hour={signal.hour} />
              </span>
              <span className="font-mono text-xs text-[var(--muted)]">
                ({formatHour(signal.hour)}:45 Brk)
              </span>
            </div>
          </div>
          <span className="font-mono text-xs text-[var(--muted)]">{signal.date}</span>
        </div>
      </div>

      <div className="border-b border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-4">
        <div className="terminal-kicker mb-1.5 text-[var(--muted)]">
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

      <div className={`px-4 py-3 ${isBuy ? "bg-[var(--terminal-accent)]/[0.035]" : isSell ? "bg-[var(--terminal-danger)]/[0.035]" : ""}`}>
        {activePairs.map((pair) => (
          <PairBadge key={pair} pair={pair} direction={getPairDir(pair)} />
        ))}
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
        <div className="border-t border-[var(--panel-border)] bg-[var(--terminal-warning)]/[0.06] px-4 py-3">
          <p className="text-xs leading-relaxed text-[var(--foreground)]">{hourNote}</p>
        </div>
      )}
    </article>
  );
}

function LockedVerdict({ locale }: { locale: "VN" | "EN" }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl border border-dashed border-[var(--panel-border)] bg-[var(--surface)] px-3.5 py-3">
      <div className="flex items-center gap-3">
        <span className="text-lg" aria-hidden="true">🔒</span>
        <div>
          <div className="text-sm font-black text-[var(--foreground)]">
            {locale === "EN" ? "VIP only" : "Chỉ VIP"}
          </div>
          <div className="text-[10px] font-mono font-bold uppercase tracking-[0.16em] text-[var(--muted)]">
            {locale === "EN" ? "Unlock to view" : "Mở khóa để xem"}
          </div>
        </div>
      </div>
      <span className="rounded-md border border-[var(--panel-border)] bg-[var(--surface-raised)] px-2.5 py-1 font-mono text-[10px] font-black uppercase text-[var(--muted)]">
        {locale === "EN" ? "Locked" : "Khóa"}
      </span>
    </div>
  );
}
