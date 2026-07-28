"use client";

import { getEntryTimeLabel, getSignalColor, getSignalLabel, getSignalTime } from "@/lib/constants";
import { verifiedBrokerTimeToLocal } from "@/lib/broker-time";
import type { Signal } from "@/lib/types";
import { useLocale } from "./LocaleProvider";
import { PairBadge } from "./PairBadge";

const VALID_TIME = /^\d{2}:\d{2}$/;

/** Return the correct pair list for a given hour slot. */
function defaultPairsForHour(hour: number): string[] {
  if ([3, 6, 9].includes(hour)) {
    return ["XAUUSD", "GBPAUD", "XAUUSD2"];
  }
  if ([12, 14, 16].includes(hour)) {
    return ["XAUUSD", "GBPUSD", "XAUUSD2"];
  }
  return [];
}

/** Resolve local (Vietnam) time, falling back to broker-time conversion. */
function resolveLocalTime(
  signal: Signal,
  brokerTime: string | null | undefined,
): string | null {
  return verifiedBrokerTimeToLocal({
    date: signal.date,
    signalTime: signal.signal_time,
    signalAtUtc: signal.signal_at_utc,
    brokerUtcOffset: signal.broker_utc_offset,
    brokerClockVerified: signal.broker_clock_verified,
  }, brokerTime);
}

export function SignalCard({ signal, isVIP = false }: { signal: Signal; isVIP?: boolean }) {
  const { locale } = useLocale();
  const signalTime = VALID_TIME.test(signal.signal_time || "")
    ? signal.signal_time as string
    : getSignalTime(signal.hour, signal.date);
  const entryTime = VALID_TIME.test(signal.entry_time || "")
    ? signal.entry_time as string
    : signal.ts === 0 ? getEntryTimeLabel(signal.hour, signal.date) : "—";
  const localSignalTime = resolveLocalTime(
    signal,
    signal.signal_time,
  );
  const localEntryTime = resolveLocalTime(
    signal,
    signal.entry_time,
  );
  const pairs = defaultPairsForHour(signal.hour);
  const isSell = signal.signal === "SELL";
  const isBuy = signal.signal === "BUY";

  const getPairDirection = (pair: string) => {
    if (!isVIP) return "locked";
    return signal.pair_dirs?.[pair] || "-";
  };

  return (
    <article className="terminal-panel group signal-rail relative overflow-hidden rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] transition-all duration-200 hover:border-[var(--terminal-accent)]/40">
      <header className="border-b border-[var(--panel-border)] bg-[var(--surface)] px-4 py-3">
        <div className="flex items-start justify-between gap-3">
          <div className="grid min-w-0 flex-1 grid-cols-2 gap-3">
            <TimeBlock
              label={locale === "EN" ? "Signal" : "Phát signal"}
              brokerTime={signalTime}
              localTime={localSignalTime}
            />
            <TimeBlock
              label={locale === "EN" ? "Entry" : "Vào lệnh"}
              brokerTime={entryTime}
              localTime={localEntryTime}
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
      </div>
    </article>
  );
}

function TimeBlock({
  label,
  brokerTime,
  localTime,
}: {
  label: string;
  brokerTime: string;
  localTime: string | null;
}) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] font-bold uppercase tracking-wider text-[var(--terminal-accent)]">{label}</div>
      {localTime ? (
        <>
          <div className="mt-0.5 font-mono text-lg font-black tabular-nums text-[var(--foreground)]">
            {localTime}
            <span className="ml-1 text-[9px] font-bold uppercase text-[var(--muted)]">VN</span>
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
