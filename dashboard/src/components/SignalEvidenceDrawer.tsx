"use client";

import { useEffect, useRef } from "react";
import type {
  SignalEvidenceV3,
  SignalEvidence,
  SignalEvidenceUnion,
  DDirectionEvidence,
  H1SignalEvidence,
  XauEntryTimingEvidence,
  EvidenceCandle,
} from "@/lib/types";
import { isSignalEvidenceV3 } from "@/lib/types";
import { ACTIVE_SIGNAL_LOGIC_VERSION } from "@/lib/signal-display";
import { useLocale } from "./LocaleProvider";

const FOCUSABLE_SELECTOR =
  "button:not([disabled]), a[href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])";

interface Props {
  evidence: SignalEvidenceUnion | null;
  loading: boolean;
  error: string | null;
  open: boolean;
  onClose: () => void;
  date: string;
  hour: number;
  version: number;
  symbol: string | null;
}

export function SignalEvidenceDrawer(props: Props) {
  const { evidence, loading, error, open, onClose, date, hour, version, symbol } = props;
  const { locale } = useLocale();
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    drawerRef.current?.querySelector<HTMLElement>("button")?.focus();
    return () => {
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
        return;
      }
      if (event.key !== "Tab" || !drawerRef.current) return;
      const focusable = [...drawerRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)];
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  const currentSymbol = symbol || (evidence && "symbol" in evidence && typeof evidence.symbol === "string" ? evidence.symbol : "XAUUSD");

  return (
    <div
      className="fixed inset-0 z-50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="signal-evidence-title"
    >
      <button
        type="button"
        className="fixed inset-0 cursor-default bg-black/65 backdrop-blur-sm"
        onClick={onClose}
        aria-label={locale === "EN" ? "Close evidence" : "Đóng bằng chứng"}
      />
      <div
        ref={drawerRef}
        className="fixed inset-y-0 right-0 flex w-[min(640px,94vw)] flex-col overflow-hidden border-l border-[var(--panel-border)] bg-[var(--surface)] shadow-2xl max-md:inset-x-0 max-md:bottom-0 max-md:top-auto max-md:h-[90dvh] max-md:w-full max-md:rounded-t-2xl max-md:border-l-0 max-md:border-t"
      >
        <DrawerHeader
          date={date}
          hour={hour}
          symbol={currentSymbol}
          version={evidence?.logic_version || version}
          locale={locale}
          onClose={onClose}
        />
        <div className="flex-1 overflow-y-auto px-5 py-5">
          {loading && (
            <StatusText text={locale === "EN" ? "Loading evidence…" : "Đang tải bằng chứng…"} />
          )}
          {error && (
            <div className="rounded-lg border border-[var(--terminal-danger)]/40 bg-[var(--terminal-danger)]/10 px-4 py-3 text-sm text-[var(--terminal-danger)]">
              {error}
            </div>
          )}
          {evidence && !loading && !error && (
            <EvidenceContent evidence={evidence} currentSymbol={currentSymbol} locale={locale} />
          )}
          {!loading && !error && !evidence && (
            <StatusText text={locale === "EN" ? "No evidence available" : "Không có bằng chứng"} />
          )}
        </div>
      </div>
    </div>
  );
}

function DrawerHeader({
  date,
  hour,
  symbol,
  version,
  locale,
  onClose,
}: {
  date: string;
  hour: number;
  symbol: string;
  version?: number;
  locale: "VN" | "EN";
  onClose: () => void;
}) {
  return (
    <header className="flex items-center justify-between border-b border-[var(--panel-border)] bg-[var(--surface-raised)] px-5 py-4">
      <div>
        <div className="flex items-center gap-2">
          <span id="signal-evidence-title" className="font-mono text-base font-black text-[var(--foreground)]">
            {symbol}
          </span>
          <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--terminal-accent)]">
            SIGNAL EVIDENCE · v{version || ACTIVE_SIGNAL_LOGIC_VERSION}
          </span>
        </div>
        <div className="mt-1 font-mono text-xs text-[var(--muted)]">
          {date} · H={hour}
        </div>
      </div>
      <button
        type="button"
        onClick={onClose}
        className="flex min-h-11 min-w-11 items-center justify-center rounded-lg p-2 text-[var(--muted)] transition-colors hover:bg-[var(--surface)] hover:text-[var(--foreground)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)]"
        aria-label={locale === "EN" ? "Close" : "Đóng"}
      >
        <span aria-hidden="true" className="text-xl leading-none">
          ×
        </span>
      </button>
    </header>
  );
}

function EvidenceContent({
  evidence,
  currentSymbol,
  locale,
}: {
  evidence: SignalEvidenceUnion;
  currentSymbol: string;
  locale: "VN" | "EN";
}) {
  if (isSignalEvidenceV3(evidence)) {
    return <EvidenceV3Content evidence={evidence} symbol={currentSymbol} locale={locale} />;
  }
  return <LegacyEvidenceContent evidence={evidence as SignalEvidence} locale={locale} />;
}

function EvidenceV3Content({
  evidence,
  symbol,
  locale,
}: {
  evidence: SignalEvidenceV3;
  symbol: string;
  locale: "VN" | "EN";
}) {
  const isXau = symbol === "XAUUSD";
  const dayModeLabel = formatDayModeLabel(evidence.day_mode);
  const isOppositeBranch =
    evidence.day_mode_source_branch &&
    evidence.current_entry_branch &&
    evidence.day_mode_source_branch !== evidence.current_entry_branch;

  return (
    <div className="space-y-6">
      {/* SECTION 1: DAY MODE */}
      <section className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)]/60 p-4 font-mono text-xs space-y-3">
        <div className="flex items-center justify-between">
          <span className="terminal-kicker text-[var(--terminal-accent)]">
            SECTION 1 · DAY MODE
          </span>
          <span className="rounded bg-[var(--terminal-accent)]/15 px-2 py-0.5 text-[10px] font-bold text-[var(--terminal-accent)]">
            {evidence.day_mode ? "RESOLVED" : "UNRESOLVED"}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-3 pt-1 text-xs">
          <div>
            <div className="text-[var(--muted)] text-[10px]">Mode</div>
            <div className="font-black text-sm text-[var(--foreground)]">{dayModeLabel}</div>
          </div>
          <div>
            <div className="text-[var(--muted)] text-[10px]">Anchored at</div>
            <div className="font-bold text-[var(--foreground)]">
              {evidence.day_mode_source_hour !== null
                ? `H${evidence.day_mode_source_hour} · ${evidence.day_mode_source_entry_time || "—"}`
                : "—"}
            </div>
          </div>
          <div>
            <div className="text-[var(--muted)] text-[10px]">Current Entry</div>
            <div className="font-bold text-[var(--foreground)]">
              {evidence.current_entry_time || "—"} ({evidence.current_entry_branch || "—"})
            </div>
          </div>
          <div>
            <div className="text-[var(--muted)] text-[10px]">Branch Relation</div>
            <div className={`font-bold ${isOppositeBranch ? "text-[var(--terminal-warning)]" : "text-[var(--terminal-accent)]"}`}>
              {evidence.current_entry_branch === "H_49"
                ? "H:49 (Previous H1)"
                : isOppositeBranch
                ? (locale === "EN" ? "Opposite Branch" : "Khác nhánh (Đảo)")
                : (locale === "EN" ? "Same Branch" : "Cùng nhánh (Giữ)")}
            </div>
          </div>
        </div>
      </section>

      {/* SECTION 2: SIGNAL SOURCE CANDLE */}
      <section className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)]/60 p-4 font-mono text-xs space-y-3">
        <div className="flex items-center justify-between">
          <span className="terminal-kicker text-[var(--terminal-accent)]">
            SECTION 2 · SIGNAL SOURCE
          </span>
          <span className="font-bold text-[var(--foreground)]">
            {evidence.primary_source || "D_DIRECTION"}
          </span>
        </div>

        {evidence.primary_source === "PREVIOUS_COMPLETED_H1" && evidence.h1_evidence ? (
          <H1CandleSection h1Evidence={evidence.h1_evidence} locale={locale} />
        ) : (
          <DCandleSection dEvidence={evidence.d_evidence} locale={locale} />
        )}
      </section>

      {/* SECTION 3: FINAL PATH */}
      <section className="rounded-xl border border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/[0.05] p-4 font-mono text-xs space-y-2">
        <span className="terminal-kicker text-[var(--terminal-accent)]">
          SECTION 3 · PATH DERIVATION
        </span>
        <div className="flex items-center gap-2 font-black text-sm text-[var(--foreground)] flex-wrap pt-1">
          <span>{evidence.primary_direction || "WAIT"}</span>
          <span className="text-[var(--muted)]">→</span>
          <span className="text-[var(--terminal-accent)]">{evidence.primary_action || "WAIT"}</span>
          <span className="text-[var(--muted)]">→</span>
          <span className="text-base text-[var(--foreground)]">{evidence.direction}</span>
        </div>
      </section>

      {/* SECTION 4: WEEKDAY ADJUSTMENT */}
      <section className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)]/60 p-4 font-mono text-xs space-y-1">
        <span className="terminal-kicker text-[var(--muted)]">
          SECTION 4 · WEEKDAY ADJUSTMENT
        </span>
        <div className="font-bold text-[var(--foreground)] pt-1">
          {evidence.weekday_adjustment_applied
            ? `APPLIED: ${evidence.weekday_adjustment_rule}`
            : (locale === "EN" ? "No weekday adjustment" : "Không đảo bổ sung theo thứ")}
        </div>
      </section>

      {/* SECTION 5: ENTRY TIMING ENGINE */}
      <section className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)]/60 p-4 font-mono text-xs space-y-3">
        <div className="flex items-center justify-between">
          <span className="terminal-kicker text-[var(--terminal-accent)]">
            SECTION 5 · ENTRY TIMING
          </span>
          <span className="rounded bg-[var(--terminal-warning)]/15 border border-[var(--terminal-warning)]/30 px-2 py-0.5 text-[9px] font-bold text-[var(--terminal-warning)] uppercase">
            ENTRY ENGINE ONLY
          </span>
        </div>
        <p className="text-[11px] text-[var(--muted)]">
          {locale === "EN"
            ? "Used only for entry timing determination, NOT for BUY/SELL signal direction."
            : "Chỉ dùng để chọn giờ vào lệnh (Entry Time), KHÔNG quyết định hướng BUY/SELL."}
        </p>

        {isXau && evidence.entry_timing ? (
          <XauEntryTimingSection timing={evidence.entry_timing} locale={locale} />
        ) : (
          <div className="pt-2 text-xs font-bold text-[var(--foreground)]">
            {locale === "EN" ? "Entry schedule:" : "Lịch vào lệnh:"} NEXT_FULL_BROKER_HOUR ({evidence.current_entry_time || "H+1:00"})
          </div>
        )}
      </section>
    </div>
  );
}

function DCandleSection({ dEvidence, locale }: { dEvidence?: DDirectionEvidence | null; locale: "VN" | "EN" }) {
  if (!dEvidence) {
    return <StatusText text={locale === "EN" ? "D-Direction data unresolved" : "Chưa có dữ liệu D-Direction"} />;
  }
  const candle = dEvidence.candle;
  const dDir = dEvidence.d_direction || "WAIT";

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div><span className="text-[var(--muted)]">Session Date: </span><span className="font-bold">{dEvidence.session_date || dEvidence.target_date}</span></div>
        <div><span className="text-[var(--muted)]">D Direction: </span><span className="font-black text-[var(--foreground)]">{dDir}</span></div>
      </div>
      <SingleCandleChart candle={candle} direction={dDir} label={`D H4 20:00 (${dEvidence.d_candle_open_time || "20:00"})`} />
    </div>
  );
}

function H1CandleSection({ h1Evidence, locale }: { h1Evidence: H1SignalEvidence; locale: "VN" | "EN" }) {
  const dir = h1Evidence.direction || "DOJI";
  const candle = {
    open: h1Evidence.open,
    high: h1Evidence.high,
    low: h1Evidence.low,
    close: h1Evidence.close,
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div><span className="text-[var(--muted)]">H1 Window: </span><span className="font-bold">{h1Evidence.open_time} → {h1Evidence.close_time}</span></div>
        <div><span className="text-[var(--muted)]">H1 Direction: </span><span className="font-black text-[var(--foreground)]">{dir}</span></div>
      </div>
      <SingleCandleChart candle={candle} direction={dir} label={`Completed H1 (${h1Evidence.open_time} - ${h1Evidence.close_time})`} />
    </div>
  );
}

function SingleCandleChart({
  candle,
  direction,
  label,
}: {
  candle?: { open: number | null; high: number | null; low: number | null; close: number | null } | null;
  direction: string;
  label: string;
}) {
  if (!candle || candle.open === null || candle.close === null || candle.high === null || candle.low === null) {
    return <StatusText text="Candle data unavailable" />;
  }

  const isUp = candle.close >= candle.open;
  const isDoji = direction === "DOJI" || Math.abs(candle.close - candle.open) < 0.0001;
  const color = isDoji
    ? "var(--terminal-warning)"
    : isUp || direction === "BUY" || direction === "TANG"
    ? "var(--terminal-accent)"
    : "var(--terminal-danger)";

  const openY = 30;
  const closeY = isUp ? 60 : 60;
  const highY = 15;
  const lowY = 85;

  return (
    <div className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface)] p-3 space-y-2">
      <div className="flex items-center justify-between text-[11px]">
        <span className="font-bold text-[var(--foreground)]">{label}</span>
        <span className="font-bold" style={{ color }}>{direction}</span>
      </div>
      <div className="flex items-center justify-between gap-4">
        <svg width="120" height="100" viewBox="0 0 120 100" className="mx-auto">
          <line x1="60" y1={highY} x2="60" y2={lowY} stroke={color} strokeWidth="2" />
          <rect x="42" y={Math.min(openY, closeY)} width="36" height={Math.max(Math.abs(closeY - openY), 4)} fill={isDoji ? "none" : color} stroke={color} strokeWidth="2" />
          <circle cx="60" cy={openY} r="3" fill="var(--foreground)" />
          <circle cx="60" cy={closeY} r="3" fill="var(--foreground)" />
        </svg>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] font-mono">
          <span className="text-[var(--muted)]">Open:</span><span className="text-right font-bold">{formatPrice(candle.open)}</span>
          <span className="text-[var(--muted)]">High:</span><span className="text-right font-bold">{formatPrice(candle.high)}</span>
          <span className="text-[var(--muted)]">Low:</span><span className="text-right font-bold">{formatPrice(candle.low)}</span>
          <span className="text-[var(--muted)]">Close:</span><span className="text-right font-bold text-[var(--foreground)]">{formatPrice(candle.close)}</span>
        </div>
      </div>
    </div>
  );
}

function XauEntryTimingSection({ timing, locale }: { timing: XauEntryTimingEvidence; locale: "VN" | "EN" }) {
  const l2 = timing.layer2;
  const l3 = timing.layer3;

  return (
    <div className="space-y-3 pt-1">
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div><span className="text-[var(--muted)]">Entry Time: </span><span className="font-black text-[var(--terminal-accent)]">{timing.entry_time || "—"}</span></div>
        <div><span className="text-[var(--muted)]">Entry State: </span><span className="font-bold">{timing.entry_state}</span></div>
      </div>

      {l2 && (
        <div className="space-y-1">
          <div className="text-[10px] font-bold text-[var(--muted)]">LAYER 2 (BT H:11)</div>
          <div className="flex gap-2">
            {l2.candles?.map((c, i) => (
              <div key={i} className="flex-1 rounded border border-[var(--panel-border)] bg-[var(--surface)] p-2 text-center text-[10px]">
                <div className="text-[var(--muted)]">{c.open_time}</div>
                <div className="font-bold">{c.direction || "—"}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      {l3 && (
        <div className="space-y-1">
          <div className="text-[10px] font-bold text-[var(--muted)]">LAYER 3 (SW PENDING)</div>
          <div className="flex gap-2">
            {l3.candles?.map((c, i) => (
              <div key={i} className="flex-1 rounded border border-[var(--panel-border)] bg-[var(--surface)] p-2 text-center text-[10px]">
                <div className="text-[var(--muted)]">{c.open_time}</div>
                <div className="font-bold">{c.direction || "—"}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function LegacyEvidenceContent({ evidence, locale }: { evidence: SignalEvidence; locale: "VN" | "EN" }) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] p-4 font-mono text-xs">
        <h3 className="font-bold text-[var(--foreground)] mb-2">Legacy Signal Evidence (v72)</h3>
        <dl className="grid grid-cols-2 gap-2">
          <dt className="text-[var(--muted)]">Symbol</dt><dd className="font-bold">{evidence.symbol}</dd>
          <dt className="text-[var(--muted)]">Direction</dt><dd className="font-bold">{evidence.direction || "WAIT"}</dd>
          <dt className="text-[var(--muted)]">Entry Time</dt><dd className="font-bold">{evidence.entry_time || "—"}</dd>
        </dl>
      </div>
    </div>
  );
}

function formatDayModeLabel(mode: string | null): string {
  if (!mode) return "UNRESOLVED";
  if (mode === "DAY_MODE_H11") return "DAY_MODE_H11 (H:11)";
  if (mode === "DAY_MODE_H_PLUS_1_25") return "DAY_MODE_H_PLUS_1_25 (H+1:25)";
  return mode;
}

function formatPrice(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return Number(value).toFixed(2);
}

function StatusText({ text }: { text: string }) {
  return (
    <div className="flex min-h-32 items-center justify-center rounded-xl border border-dashed border-[var(--panel-border)] px-4 text-center text-sm text-[var(--muted)] font-mono">
      {text}
    </div>
  );
}
