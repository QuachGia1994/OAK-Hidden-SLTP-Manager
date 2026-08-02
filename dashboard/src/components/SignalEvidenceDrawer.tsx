"use client";

import { useEffect, useRef, type ReactNode } from "react";
import type {
  SignalEvidenceV3,
  SignalEvidenceUnion,
  DDirectionEvidence,
  H1SignalEvidence,
  XauEntryTimingEvidence,
  M30EvidenceLayer,
  EvidenceCandle,
  H49H1Evidence,
} from "@/lib/types";
import { isSignalEvidenceV3 } from "@/lib/types";
import { ACTIVE_SIGNAL_LOGIC_VERSION } from "@/lib/signal-display";
import { useLocale } from "./LocaleProvider";
import { getT, formatDirection, formatBranch } from "@/lib/translations";
import { isMissingInputWaitReason } from "@/lib/signal-integrity";

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
  waitReasons?: Record<string, string>;
  rebuildState?: string;
  rebuildStateReason?: string;
  failureReason?: string | null;
}

export function SignalEvidenceDrawer(props: Props) {
  const { evidence, loading, error, open, onClose, date, hour, version, symbol,
    waitReasons, rebuildState, rebuildStateReason, failureReason } = props;
  const { locale } = useLocale();
  const t = getT(locale).evidence;
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

  const currentSymbol = "XAUUSD";
  if (!open) return null;

  const missingWaitReasons = Object.entries(waitReasons || {})
    .filter(([, reason]) => isMissingInputWaitReason(reason))
    .map(([pair, reason]) => ({ pair, reason }));
  const incomplete =
    rebuildState === "REBUILD_INCOMPLETE"
    || missingWaitReasons.length > 0
    || isMissingInputWaitReason(failureReason);
  const historyT = getT(locale).history;

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
        aria-label={t.closeDrawer}
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
          {incomplete && (
            <div className="mb-4 space-y-2 rounded-xl border border-[var(--terminal-danger)]/40 bg-[var(--terminal-danger)]/10 px-4 py-3 font-mono text-xs">
              <div className="flex items-center gap-2">
                <span className="font-black uppercase tracking-wider text-[var(--terminal-danger)]">
                  {historyT.incompleteBadge}
                </span>
                {rebuildStateReason && (
                  <span className="text-[10px] font-bold text-[var(--terminal-warning)]">
                    {rebuildStateReason}
                  </span>
                )}
              </div>
              {missingWaitReasons.map(({ pair, reason }) => (
                <div key={pair} className="flex items-center justify-between gap-2">
                  <span className="text-[var(--muted)]">{historyT.waitReason} · {pair}</span>
                  <span className="font-black text-[var(--terminal-warning)]">{reason}</span>
                </div>
              ))}
              {missingWaitReasons.length === 0 && failureReason && (
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[var(--muted)]">{historyT.waitReason}</span>
                  <span className="font-black text-[var(--terminal-warning)]">{failureReason}</span>
                </div>
              )}
            </div>
          )}
          {loading && (
            <StatusText text={t.loading} />
          )}
          {error && (
            <div className="rounded-lg border border-[var(--terminal-danger)]/40 bg-[var(--terminal-danger)]/10 px-4 py-3 text-sm text-[var(--terminal-danger)]">
              {t.errorPrefix} {error}
            </div>
          )}
          {evidence && !loading && !error && (
            <EvidenceContent evidence={evidence} currentSymbol={currentSymbol} locale={locale} />
          )}
          {!loading && !error && !evidence && (
            <StatusText text={t.noEvidence} />
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
            {getT(locale).evidence.titleSuffix} · v{version || ACTIVE_SIGNAL_LOGIC_VERSION}
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
    if (evidence.evidence_schema_version === 9 || evidence.evidence_schema_version === 10) {
      return <EvidenceV87Content evidence={evidence} symbol={currentSymbol} locale={locale} />;
    }
    return <EvidenceV3Content evidence={evidence} symbol={currentSymbol} locale={locale} />;
  }
  return (
    <StatusText
      text={locale === "EN" ? "Evidence version is not supported" : "Phiên bản evidence không được hỗ trợ"}
    />
  );
}

function EvidenceV87Content({
  evidence,
  symbol,
  locale,
}: {
  evidence: SignalEvidenceV3;
  symbol: string;
  locale: "VN" | "EN";
}) {
  const timing = evidence.entry_timing;
  const t = getT(locale).evidence;
  const entryBranch = formatBranch(evidence.current_entry_branch || evidence.entry_branch || timing?.entry_branch);
  const referenceSymbol = evidence.reference_d_symbol || "GBPUSD";
  const layer1Source = evidence.base_signal_source === "PREVIOUS_XAU_H1_REVERSED"
    ? t.sourcePreviousH1Reversed
    : evidence.base_signal_source === "REFERENCE_D_DAY_MODE"
    ? t.sourceReferenceDDayMode
    : t.sourceWaitingForD;
  const isH49Branch = (evidence.current_entry_branch || evidence.entry_branch || timing?.entry_branch) === "H_49";
  const h49 = evidence.h49_h1_evidence;
  return (
    <div className="space-y-4 font-mono text-xs">
      {isH49Branch && h49 ? (
        <H49H1Section h49={h49} locale={locale} />
      ) : (
        <EvidenceSection title={t.sectionLayer1}>
          <p>{t.referenceD}: {referenceSymbol} · <strong>{formatDirection(evidence.reference_d_direction, t)}</strong></p>
          <p>{t.entryBranch}: {entryBranch}</p>
          <p>{t.rule}: {layer1Source}</p>
          <p>{t.layer1Output}: <strong>{formatDirection(evidence.core_signal, t)}</strong></p>
        </EvidenceSection>
      )}
      <EvidenceSection title={t.sectionLayers23}>
        <p>{t.source}: XAUUSD · {timing?.timeframe || "M30"}</p>
        <p>{t.selected}: <strong>{evidence.current_entry_time || timing?.entry_time || "WAIT"}</strong> · {entryBranch}</p>
        <p>{t.sharedPlan}</p>
        {timing?.layer2 && <CandleMiniTable label="LAYER 2" layer={timing.layer2} />}
        {timing?.layer3 && <CandleMiniTable label="LAYER 3" layer={timing.layer3} />}
      </EvidenceSection>
      <EvidenceSection title={t.sectionLayer4}>
        <p>{t.coreToFinal}: <strong>{formatDirection(evidence.final_signal || evidence.direction, t)}</strong></p>
        <p>{evidence.final_reverse_applied ? `${t.reverse} · ${evidence.final_reverse_reason || "—"}` : t.noFinalReverse}</p>
      </EvidenceSection>
    </div>
  );
}

function EvidenceSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)]/60 p-4 space-y-2">
      <div className="terminal-kicker text-[var(--terminal-accent)]">{title}</div>
      {children}
    </section>
  );
}

function H49H1Section({ h49, locale }: { h49: H49H1Evidence; locale: "VN" | "EN" }) {
  const t = getT(locale).evidence;
  const dir = h49.candle_direction || "WAIT";
  const reversed = h49.reversed_signal || "WAIT";
  const isUp = dir === "TANG";
  const isDoji = dir === "DOJI";
  const color = isDoji
    ? "var(--terminal-warning)"
    : isUp
    ? "var(--terminal-accent)"
    : "var(--terminal-danger)";
  const reversedColor = reversed === "BUY"
    ? "var(--terminal-accent)"
    : reversed === "SELL"
    ? "var(--terminal-danger)"
    : "var(--terminal-warning)";
  const num = (v: string | number | null | undefined): number | null => {
    if (v === null || v === undefined || v === "") return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  };
  const candle = { open: num(h49.open_exact), high: num(h49.high_exact), low: num(h49.low_exact), close: num(h49.close_exact) };

  return (
    <section className="rounded-xl border border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/[0.05] p-4 space-y-2">
      <div className="terminal-kicker text-[var(--terminal-accent)]">
        {t.sectionH49H1}
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <span className="text-[var(--muted)]">{t.h49Window}: </span>
          <span className="font-bold">{h49.broker_open_at} → {h49.broker_close_at}</span>
        </div>
        <div>
          <span className="text-[var(--muted)]">{t.h49Source}: </span>
          <span className="font-bold">{h49.source_symbol}</span>
        </div>
        <div>
          <span className="text-[var(--muted)]">{t.h49Direction}: </span>
          <span className="font-black" style={{ color }}>{formatDirection(dir, t)}</span>
        </div>
        <div>
          <span className="text-[var(--muted)]">{t.h49Reversed}: </span>
          <span className="font-black" style={{ color: reversedColor }}>{formatDirection(reversed, t)}</span>
        </div>
      </div>
      <div className="flex items-center justify-between gap-4 pt-1">
        <svg width="120" height="100" viewBox="0 0 120 100" className="mx-auto">
          <line x1="60" y1="15" x2="60" y2="85" stroke={color} strokeWidth="2" />
          <rect x="42" y={isUp ? 30 : 60} width="36" height="30" fill={isDoji ? "none" : color} stroke={color} strokeWidth="2" />
          <circle cx="60" cy="30" r="3" fill="var(--foreground)" />
          <circle cx="60" cy="60" r="3" fill="var(--foreground)" />
        </svg>
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px] font-mono">
          <span className="text-[var(--muted)]">{t.h49Open}:</span><span className="text-right font-bold">{formatPrice(candle.open)}</span>
          <span className="text-[var(--muted)]">{t.h49High}:</span><span className="text-right font-bold">{formatPrice(candle.high)}</span>
          <span className="text-[var(--muted)]">{t.h49Low}:</span><span className="text-right font-bold">{formatPrice(candle.low)}</span>
          <span className="text-[var(--muted)]">{t.h49Close}:</span><span className="text-right font-bold text-[var(--foreground)]">{formatPrice(candle.close)}</span>
        </div>
      </div>
      {h49.failure_reason && (
        <p className="text-[var(--terminal-warning)]">
          {h49.failure_reason === "H49_H1_DOJI"
            ? t.h49Doji
            : h49.failure_reason === "H49_H1_MISSING"
            ? t.h49Missing
            : h49.failure_reason}
        </p>
      )}
    </section>
  );
}

function CandleMiniTable({ label, layer }: { label: string; layer: M30EvidenceLayer }) {
  return (
    <div className="mt-2 overflow-x-auto rounded border border-[var(--panel-border)]/60">
      <div className="border-b border-[var(--panel-border)]/60 px-2 py-1 font-bold text-[10px] text-[var(--muted)]">{label}</div>
      <table className="w-full text-left text-[11px]"><thead><tr><th className="px-2 py-1">Candle</th><th className="px-2 py-1">Open</th><th className="px-2 py-1">Direction</th></tr></thead>
        <tbody>{(layer.candles || []).map((candle) => <tr key={`${candle.role}-${candle.open_time}`}><td className="px-2 py-1">{candle.role || "—"}</td><td className="px-2 py-1">{candle.open_time || "—"}</td><td className="px-2 py-1">{candle.direction || "WAIT"}</td></tr>)}</tbody>
      </table>
      <div className="border-t border-[var(--panel-border)]/60 px-2 py-1">Group: {layer.group || "WAIT"}</div>
    </div>
  );
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
  const dayModeLabel = formatDayModeLabel(evidence.day_mode ?? null);
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

        {evidence.entry_timing ? (
          <XauEntryTimingSection timing={evidence.entry_timing} locale={locale} />
        ) : (
          <div className="pt-2 text-xs font-bold text-[var(--foreground)]">
            {locale === "EN" ? "Common XAUUSD Entry:" : "Entry chung XAUUSD:"} {evidence.current_entry_time || "WAIT"}
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
          <div className="text-[10px] font-bold text-[var(--muted)]">LAYER 2 · {l2.group || "WAIT"} ({timing.timeframe})</div>
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
          <div className="text-[10px] font-bold text-[var(--muted)]">LAYER 3 · {l3.group || "WAIT"} ({timing.timeframe})</div>
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
