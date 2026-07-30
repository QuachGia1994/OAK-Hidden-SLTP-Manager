"use client";

import { useState, useEffect } from "react";
import { SignalCard } from "./SignalCard";
import { DDirectionPanel } from "./DDirectionPanel";
import type { Signal, DDirectionSnapshotV2 } from "@/lib/types";
import { useLocale } from "./LocaleProvider";
import { getSlotTimeValue } from "@/lib/constants";

function weekdayLabel(dateStr: string, locale: "VN" | "EN"): string {
  const [year, month, dayOfMonth] = dateStr.split("-").map(Number);
  const day = new Date(year, month - 1, dayOfMonth).getDay();
  const labels = locale === "EN"
    ? ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    : ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];
  return labels[day];
}

interface CollapsibleDayProps {
  date: string;
  signals: Signal[];
  isVIP: boolean;
  defaultOpen?: boolean;
  initialDSnapshot?: DDirectionSnapshotV2 | null;
}

export function CollapsibleDay({ date, signals, isVIP, defaultOpen = false, initialDSnapshot }: CollapsibleDayProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [dSnapshot, setDSnapshot] = useState<DDirectionSnapshotV2 | null>(initialDSnapshot || null);
  const { locale } = useLocale();

  useEffect(() => {
    if (open && !dSnapshot) {
      fetch(`/api/signals/d-direction?date=${date}`)
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (data && data.symbols) setDSnapshot(data);
        })
        .catch(() => {});
    }
  }, [open, date, dSnapshot]);

  const daySignals = [...signals].sort(
    (a, b) => getSlotTimeValue(b.hour, b.signal_time || null) - getSlotTimeValue(a.hour, a.signal_time || null),
  );
  const weekday = weekdayLabel(date, locale);
  const verdictCounts = daySignals.reduce(
    (counts, signal) => {
      if (signal.signal === "BUY") counts.buy += 1;
      else if (signal.signal === "SELL") counts.sell += 1;
      else counts.wait += 1;
      return counts;
    },
    { buy: 0, sell: 0, wait: 0 },
  );

  return (
    <section className="terminal-panel history-day overflow-hidden rounded-xl">
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="history-day-toggle group flex w-full items-center gap-3 px-4 py-3.5 text-left sm:px-5"
      >
        <svg
          className={`h-4 w-4 shrink-0 text-[color:var(--terminal-accent)] transition-transform duration-200 ${open ? "rotate-90" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
        </svg>
        <div className="min-w-0">
          <h2 className="font-mono text-base font-black text-[var(--foreground)]">
            {date} <span className="text-[var(--muted)]">({weekday})</span>
          </h2>
          <p className="mt-0.5 text-[11px] font-semibold text-[var(--muted)]">
            {daySignals.length} {locale === "EN" ? `signal${daySignals.length !== 1 ? "s" : ""}` : "tín hiệu"}
          </p>
        </div>
        <div className="ml-auto hidden items-center gap-3 font-mono text-xs font-bold sm:flex">
          <VerdictCount label="BUY" value={verdictCounts.buy} tone="buy" />
          <VerdictCount label="SELL" value={verdictCounts.sell} tone="sell" />
          <VerdictCount label={locale === "EN" ? "WAIT" : "CHỜ"} value={verdictCounts.wait} tone="wait" />
        </div>
        <span className="history-day-state font-mono text-xs">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <div className="history-day-content px-4 pb-4 pt-4 space-y-4">
          <DDirectionPanel snapshot={dSnapshot} date={date} locale={locale} />
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
            {daySignals.map((signal) => (
              <SignalCard
                key={`${signal.date}-${signal.hour}`}
                signal={signal}
                isVIP={isVIP}
              />
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function VerdictCount({ label, value, tone }: { label: string; value: number; tone: "buy" | "sell" | "wait" }) {
  const toneClass = {
    buy: "text-[var(--terminal-accent)]",
    sell: "text-[var(--terminal-danger)]",
    wait: "text-[var(--muted)]",
  }[tone];

  return <span className={toneClass}>{label} {value}</span>;
}
