"use client";

import {
  GBP_PAIRS,
  formatHour,
  getHourNote,
  getSignalColor,
  getSignalLabel,
  getTargetMinute,
  weekdayFromDate,
} from "@/lib/constants";
import { localizeHourNote } from "@/lib/signal-note-i18n";
import type { Signal } from "@/lib/types";
import { BrokerLocalTime } from "./BrokerLocalTime";
import { H11CandleChart } from "./H11CandleChart";
import { useLocale } from "./LocaleProvider";
import { PairBadge } from "./PairBadge";

export function SignalCard({
  signal,
  isVIP,
}: {
  signal: Signal;
  isVIP?: boolean;
}) {
  const { locale } = useLocale();
  const weekday = weekdayFromDate(signal.date);
  const isWednesday = weekday === 3;
  const rawHourNote = signal.hour_note || getHourNote(signal.hour, weekday) || "";
  const {
    translatedNote: hourNote,
    badgeText,
    descriptionText,
    hasNoGoldBadge,
  } = localizeHourNote(rawHourNote, locale);
  const showHourNote = false;

  const defaultPairs = signal.hour === 11
    ? []
    : (signal.hour === 9)
      ? ["XAUUSD", "GBPUSD", "GBPAUD"]
      : (signal.hour === 14)
        ? ["XAUUSD", "GBPUSD", "GBPAUD"]
        : (signal.hour === 2 || signal.hour === 3)
          ? (isWednesday ? ["XAUUSD"] : ["XAUUSD", "GBPAUD"])
          : ["XAUUSD"];

  const activePairs = signal.hour === 11
    ? []
    : signal.pair_dirs && Object.keys(signal.pair_dirs).length > 0
      ? Object.keys(signal.pair_dirs).filter((p) => {
          if (p === "Stock-DIRECTION" || p === "GBP-DIRECTION") return false;
          if (isWednesday && GBP_PAIRS.includes(p)) return false;
          // H=9: only XAUUSD, GBPUSD, GBPAUD
          if (signal.hour === 9 && !["XAUUSD", "GBPUSD", "GBPAUD"].includes(p)) return false;
          // H=14: only XAUUSD, GBPUSD, GBPAUD
          if (signal.hour === 14 && !["XAUUSD", "GBPUSD", "GBPAUD"].includes(p)) return false;
          return true;
        })
      : defaultPairs;

  const getPairDir = (pair: string) => {
    if (!isVIP) return "locked";
    return signal.pair_dirs?.[pair] || (["BUY", "SELL", "SW", "BT"].includes(signal.signal) ? signal.signal : "-");
  };

  const isSell = signal.signal === "SELL";
  const isBuy = signal.signal === "BUY";

  return (
    <article className="terminal-panel group signal-rail overflow-hidden rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] transition-all duration-200 hover:border-[var(--terminal-accent)]/40">
      <div className="relative border-b border-[var(--panel-border)] bg-[var(--surface)] px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[var(--terminal-accent)]">
                {locale === "EN" ? "Entry Time" : "Giờ vào lệnh"}
              </span>
              {signal.is_priority && (
                <span className="inline-flex items-center rounded-full bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-400 border border-amber-500/30">
                  ⭐ {locale === "EN" ? "Priority" : "Ưu tiên"}
                </span>
              )}
            </div>
            <div className="mt-0.5 flex flex-wrap items-baseline gap-1.5">
              <span className="font-mono text-2xl font-black tabular-nums text-[var(--foreground)]">
                <BrokerLocalTime date={signal.date} hour={signal.hour} entryTime={signal.entry_time} />
              </span>
              <span className="font-mono text-xs font-semibold text-[var(--muted)]">
                ({signal.entry_time ?? `${formatHour(signal.hour)}:${String(getTargetMinute(signal.hour)).padStart(2, '0')}`} Brk)
              </span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)]">
              {locale === "EN" ? "Slot" : "Mốc"}
            </div>
            <div className="font-mono text-xs font-bold text-[var(--foreground)]">
              H={signal.hour === 1500 ? "15:00" : signal.hour === 15 ? "15:45" : signal.hour}
            </div>
            <div className="font-mono text-[10px] text-[var(--muted)]">{signal.date}</div>
          </div>
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
        <div className="border-t border-[var(--panel-border)] bg-[var(--terminal-warning)]/[0.06] px-4 py-3 space-y-1.5">
          {badgeText && (
            <div className="inline-flex items-center gap-1.5 rounded-full border border-[var(--terminal-warning)]/40 bg-[var(--terminal-warning)]/15 px-2.5 py-0.5 font-mono text-[11px] font-bold text-[var(--terminal-warning)] shadow-sm">
              <span>{badgeText}</span>
            </div>
          )}
          {hasNoGoldBadge && (
            <div className="inline-flex items-center gap-1.5 rounded-full border border-[var(--terminal-warning)]/40 bg-[var(--terminal-warning)]/15 px-2.5 py-0.5 font-mono text-[11px] font-bold text-[var(--terminal-warning)] shadow-sm">
              <span>🚫 no-gold label</span>
            </div>
          )}
          {descriptionText && (
            <p className="text-xs leading-relaxed text-[var(--foreground)]">{descriptionText}</p>
          )}
          {(signal.hour === 11 || signal.hour === 1500) && (
            <H11CandleChart candles={signal.h11_candles} locale={locale} hour={signal.hour} />
          )}
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
