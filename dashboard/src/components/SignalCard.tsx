"use client";

import { useState, useCallback } from "react";
import { getEntryTimeLabel, getSignalColor, getSignalLabel, getSignalTime } from "@/lib/constants";
import { FormattedLocalTime, useBrowserBrokerTime } from "@/hooks/useBrowserBrokerTime";
import type { Signal, SignalEvidence } from "@/lib/types";
import { useLocale } from "./LocaleProvider";
import { PairBadge } from "./PairBadge";
import { DISPLAYED_SIGNAL_PAIRS } from "@/lib/signal-display";
import { SignalEvidenceDrawer } from "./SignalEvidenceDrawer";

const VALID_TIME = /^\d{2}:\d{2}$/;

function getPendingEntryLabel(locale: "VN" | "EN", hour: number): string {
  const time = `${String(hour).padStart(2, "0")}:45`;
  return locale === "EN" ? `Awaiting ${time} Broker candle` : `Chờ nến Broker ${time}`;
}

export function SignalCard({ signal, isVIP = false }: { signal: Signal; isVIP?: boolean }) {
  const { locale } = useLocale();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<SignalEvidence | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);

  const fetchEvidence = useCallback(async (symbol: string) => {
    setSelectedSymbol(symbol);
    setDrawerOpen(true);
    setEvidenceLoading(true);
    setEvidenceError(null);
    try {
      const res = await fetch(`/api/signals/evidence?date=${signal.date}&hour=${signal.hour}&symbol=${symbol}`);
      if (res.status === 403) {
        setEvidenceError(locale === "EN" ? "VIP access required" : "Yêu cầu quyền VIP");
        setEvidenceLoading(false);
        return;
      }
      if (res.status === 404) {
        setEvidenceError(locale === "EN" ? "No evidence data for this slot" : "Không có dữ liệu bằng chứng cho mốc này");
        setEvidenceLoading(false);
        return;
      }
      if (!res.ok) {
        setEvidenceError(locale === "EN" ? "Failed to load evidence" : "Tải bằng chứng thất bại");
        setEvidenceLoading(false);
        return;
      }
      const data = await res.json();
      setEvidence(data);
    } catch {
      setEvidenceError(locale === "EN" ? "Network error" : "Lỗi mạng");
    }
    setEvidenceLoading(false);
  }, [signal.date, signal.hour, locale]);

  const signalTime = VALID_TIME.test(signal.signal_time || "")
    ? (signal.signal_time as string)
    : getSignalTime(signal.hour, signal.date);

  const isPendingFollowup = signal.entry_state === "PENDING_FOLLOWUP";
  const entryTime = VALID_TIME.test(signal.entry_time || "")
    ? (signal.entry_time as string)
    : isPendingFollowup
    ? getPendingEntryLabel(locale, signal.hour)
    : signal.ts === 0
    ? getEntryTimeLabel(signal.hour, signal.date)
    : "—";

  const localSignalTime = useBrowserBrokerTime(
    signal,
    signalTime,
    signal.signal_at_utc ? String(signal.signal_at_utc) : null,
  );
  const localEntryTime = useBrowserBrokerTime(
    signal,
    VALID_TIME.test(signal.entry_time || "") ? signal.entry_time : null,
    signal.entry_at_utc,
  );

  const isSell = signal.signal === "SELL";
  const isBuy = signal.signal === "BUY";

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
              isPending={isPendingFollowup}
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
          isPendingFollowup ? (
            <span className="font-mono text-3xl font-black leading-none text-amber-400 animate-pulse">
              {locale === "EN" ? "PENDING" : "ĐANG CHỜ"}
            </span>
          ) : (
            <span className={`font-mono text-4xl font-black leading-none ${getSignalColor(signal.signal)}`}>
              {getSignalLabel(signal.signal, locale)}
            </span>
          )
        ) : (
          <LockedVerdict locale={locale} />
        )}
      </div>

      <div className={`px-4 py-3 ${isBuy ? "bg-[var(--terminal-accent)]/[0.035]" : isSell ? "bg-[var(--terminal-danger)]/[0.035]" : ""}`}>
        {DISPLAYED_SIGNAL_PAIRS.map((pair) => (
          <PairRow key={pair} pair={pair} signal={signal} isVIP={isVIP} onInspect={isVIP ? () => fetchEvidence(pair) : undefined} />
        ))}
      </div>

      <SignalEvidenceDrawer
        evidence={evidence}
        loading={evidenceLoading}
        error={evidenceError}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        date={signal.date}
        hour={signal.hour}
        symbol={selectedSymbol}
      />
    </article>
  );
}

function PairRow({
  pair,
  signal,
  isVIP,
  onInspect,
}: {
  pair: string;
  signal: Signal;
  isVIP: boolean;
  onInspect?: () => void;
}) {
  const direction = isVIP ? signal.pair_dirs?.[pair] || "-" : "locked";
  const brokerEntryTime = isVIP ? signal.pair_entry_times?.[pair] || null : null;
  const utcIso = isVIP ? signal.pair_entry_at_utc?.[pair] || null : null;
  const localEntryTime = useBrowserBrokerTime(signal, brokerEntryTime, utcIso);
  const state = isVIP ? signal.pair_entry_states?.[pair] || null : null;
  const label = isVIP ? signal.pair_labels?.[pair] || null : null;

  return (
    <PairBadge
      pair={pair}
      direction={direction}
      brokerEntryTime={brokerEntryTime}
      localEntryTime={localEntryTime}
      state={state}
      label={label}
      onClick={onInspect}
      hasEvidence={isVIP}
    />
  );
}

function TimeBlock({
  label,
  brokerTime,
  localTime,
  isPending,
}: {
  label: string;
  brokerTime: string;
  localTime: FormattedLocalTime | null;
  isPending?: boolean;
}) {
  return (
    <div className="min-w-0">
      <div className="text-[10px] font-bold uppercase tracking-wider text-[var(--terminal-accent)]">{label}</div>
      {isPending ? (
        <div className="mt-0.5 font-mono text-xs font-bold text-amber-400 leading-snug animate-pulse">
          {brokerTime}
        </div>
      ) : localTime ? (
        <>
          <div className="mt-0.5 font-mono text-base font-black tabular-nums text-[var(--foreground)] leading-snug">
            {localTime.time}
            <span className="ml-1 text-[9px] font-bold uppercase text-[var(--muted)]">{localTime.zoneLabel}</span>
            {localTime.dateDelta !== 0 && (
              <span className="ml-1 text-[9px] text-amber-400">{localTime.dateDelta > 0 ? "+1d" : "-1d"}</span>
            )}
          </div>
          <div className="font-mono text-[10px] font-semibold text-[var(--muted)]">{brokerTime} Broker</div>
        </>
      ) : (
        <div className="mt-0.5 font-mono text-base font-black tabular-nums text-[var(--foreground)] leading-snug">
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
          <div className="text-xs text-[var(--muted)]">
            {locale === "EN" ? "Enter access code to unlock" : "Nhập mã để xem tín hiệu thô"}
          </div>
        </div>
      </div>
    </div>
  );
}
