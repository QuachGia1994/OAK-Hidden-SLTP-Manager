"use client";

import { getEntryTimeLabel, getSignalColor, getSignalLabel, getSignalTime } from "@/lib/constants";
import { parseBrokerOffset } from "@/lib/broker-time";
import type { Signal } from "@/lib/types";
import { BrokerLocalTime } from "./BrokerLocalTime";
import { useLocale } from "./LocaleProvider";
import { PairBadge } from "./PairBadge";

const VISIBLE_GBP_SLOTS = new Set([9, 14]);
const VALID_TIME = /^\d{2}:\d{2}$/;

function defaultPairsForHour(hour: number): string[] {
  if (VISIBLE_GBP_SLOTS.has(hour)) return ["XAUUSD", "GBPUSD", "GBPAUD"];
  if (hour === 3) return ["XAUUSD", "GBPAUD"];
  return ["XAUUSD"];
}

function visiblePairs(signal: Signal): string[] {
  const pairs = Object.keys(signal.pair_dirs || {});
  if (pairs.length === 0) return defaultPairsForHour(signal.hour);
  return pairs.filter((pair) => {
    if (pair === "Stock-DIRECTION" || pair === "GBP-DIRECTION") return false;
    if (VISIBLE_GBP_SLOTS.has(signal.hour)) {
      return ["XAUUSD", "GBPUSD", "GBPAUD"].includes(pair);
    }
    return true;
  });
}

export function SignalCard({ signal, isVIP = false }: { signal: Signal; isVIP?: boolean }) {
  const { locale } = useLocale();
  const signalTime = VALID_TIME.test(signal.signal_time || "")
    ? signal.signal_time as string
    : getSignalTime(signal.hour, signal.date);
  const entryTime = VALID_TIME.test(signal.entry_time || "")
    ? signal.entry_time as string
    : signal.ts === 0 ? getEntryTimeLabel(signal.hour, signal.date) : "—";
  const pairs = visiblePairs(signal);
  const isSell = signal.signal === "SELL";
  const isBuy = signal.signal === "BUY";

  const getPairDirection = (pair: string) => {
    if (!isVIP) return "locked";
    return signal.pair_dirs?.[pair]
      || (["BUY", "SELL", "SW", "BT"].includes(signal.signal) ? signal.signal : "-");
  };

  return (
    <article className="terminal-panel group signal-rail relative overflow-hidden rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] transition-all duration-200 hover:border-[var(--terminal-accent)]/40">
      {signal.deactivated ? (
        <div className="relative z-10 border-b border-amber-500/35 bg-amber-500/15 px-4 py-2 text-center font-mono text-[11px] font-black uppercase tracking-[0.16em] text-amber-500">
          {locale === "EN" ? "DO NOT ENTER" : "KHÔNG VÀO LỆNH"}
        </div>
      ) : null}

      <div className={signal.deactivated ? "opacity-40 grayscale" : ""}>
        <header className="border-b border-[var(--panel-border)] bg-[var(--surface)] px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <div className="grid min-w-0 flex-1 grid-cols-2 gap-3">
              <TimeBlock
                label={locale === "EN" ? "Signal" : "Phát signal"}
                brokerTime={signalTime}
                signal={signal}
                utcTimestamp={signal.signal_at_utc}
              />
              <TimeBlock
                label={locale === "EN" ? "Entry" : "Vào lệnh"}
                brokerTime={entryTime}
                signal={signal}
              />
            </div>
            <div className="shrink-0 text-right">
              <div className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)]">
                {locale === "EN" ? "Slot" : "Mốc"}
              </div>
              <div className="font-mono text-xs font-bold text-[var(--foreground)]">H={signal.hour}</div>
              <div className="font-mono text-[10px] text-[var(--muted)]">{signal.date}</div>
            </div>
          </div>
          {signal.is_priority ? (
            <span className="mt-2 inline-flex rounded-md border border-amber-500/30 bg-amber-500/20 px-2.5 py-1 text-[10px] font-bold uppercase text-amber-400">
              ★ {locale === "EN" ? "Priority" : "Ưu tiên"}
            </span>
          ) : null}
        </header>

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
          {pairs.map((pair) => (
            <PairBadge key={pair} pair={pair} direction={getPairDirection(pair)} />
          ))}
          {signal.pair_dirs?.["Stock-DIRECTION"] ? (
            <PairBadge pair="Stock-DIRECTION" direction={isVIP ? signal.pair_dirs["Stock-DIRECTION"] : "locked"} />
          ) : null}
          {signal.pair_dirs?.["GBP-DIRECTION"] ? (
            <PairBadge pair="GBP-DIRECTION" direction={isVIP ? signal.pair_dirs["GBP-DIRECTION"] : "locked"} />
          ) : null}
        </div>
      </div>
    </article>
  );
}

function TimeBlock({
  label,
  brokerTime,
  signal,
  utcTimestamp,
}: {
  label: string;
  brokerTime: string;
  signal: Signal;
  utcTimestamp?: string | number | null;
}) {
  const hasLocalTime = VALID_TIME.test(brokerTime)
    && parseBrokerOffset(signal.broker_utc_offset) !== null;
  return (
    <div className="min-w-0">
      <div className="text-[10px] font-bold uppercase tracking-wider text-[var(--terminal-accent)]">{label}</div>
      {hasLocalTime ? (
        <>
          <div className="mt-0.5 font-mono text-lg font-black tabular-nums text-[var(--foreground)]">
            <BrokerLocalTime
              date={signal.date}
              brokerTime={brokerTime}
              brokerUtcOffset={signal.broker_utc_offset}
              utcTimestamp={utcTimestamp}
            />
            <span className="ml-1 text-[9px] font-bold uppercase text-[var(--muted)]">Local</span>
          </div>
          <div className="font-mono text-[10px] font-semibold text-[var(--muted)]">{brokerTime} Broker</div>
        </>
      ) : (
        <div className="mt-0.5 font-mono text-lg font-black tabular-nums text-[var(--foreground)]">
          {brokerTime} <span className="text-[9px] font-bold uppercase text-[var(--muted)]">Broker</span>
        </div>
      )}
    </div>
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
          <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-[var(--muted)]">
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
