"use client";

import { useEffect, useRef } from "react";
import type { SignalEvidence, EvidenceCandle } from "@/lib/types";
import { ACTIVE_SIGNAL_LOGIC_VERSION } from "@/lib/signal-display";
import { useLocale } from "./LocaleProvider";

interface SignalEvidenceDrawerProps {
  evidence: SignalEvidence | null;
  loading: boolean;
  error: string | null;
  open: boolean;
  onClose: () => void;
  date: string;
  hour: number;
  symbol: string | null;
}

export function SignalEvidenceDrawer({
  evidence,
  loading,
  error,
  open,
  onClose,
  date,
  hour,
  symbol,
}: SignalEvidenceDrawerProps) {
  const { locale } = useLocale();
  const drawerRef = useRef<HTMLDivElement>(null);

  // Focus trap
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement;
    const drawer = drawerRef.current;
    if (drawer) {
      const firstFocusable = drawer.querySelector<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      firstFocusable?.focus();
    }
    return () => prev?.focus();
  }, [open]);

  // Escape to close
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  // Body scroll lock
  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, [open]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label={locale === "EN" ? "Signal Evidence Inspector" : "Kiểm tra bằng chứng Signal"}>
      {/* Backdrop */}
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />

      {/* Drawer */}
      <div
        ref={drawerRef}
        className="fixed right-0 top-0 bottom-0 w-[min(520px,92vw)] bg-[var(--surface)] border-l border-[var(--panel-border)] shadow-2xl flex flex-col overflow-hidden
          max-md:bottom-0 max-md:left-0 max-md:right-0 max-md:top-auto max-md:w-full max-md:h-[88dvh] max-md:border-l-0 max-md:border-t max-md:rounded-t-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--panel-border)] bg-[var(--surface-raised)]">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-sm font-black text-[var(--foreground)]">{symbol}</span>
              <span className="text-xs font-bold uppercase tracking-wider text-[var(--terminal-accent)]">
                {locale === "EN" ? "Evidence v" : "Bằng chứng v"}
                {evidence?.logic_version || ACTIVE_SIGNAL_LOGIC_VERSION}
              </span>
            </div>
            <div className="font-mono text-sm text-[var(--foreground)]">
              {date} H={hour}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-[var(--surface)] text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
            aria-label={locale === "EN" ? "Close" : "Đóng"}
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4">
          {loading && (
            <div className="flex items-center justify-center py-12 text-[var(--muted)]">
              <svg className="w-5 h-5 animate-spin mr-2" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              {locale === "EN" ? "Loading evidence…" : "Đang tải bằng chứng…"}
            </div>
          )}
          {error && (
            <div className="rounded-lg border border-[var(--terminal-danger)]/30 bg-[var(--terminal-danger)]/10 px-4 py-3 text-sm text-[var(--terminal-danger)]">
              {error}
            </div>
          )}
          {evidence && !loading && !error && (
            <EvidenceContent evidence={evidence} locale={locale} />
          )}
          {!loading && !error && !evidence && (
            <div className="text-center py-12 text-[var(--muted)] text-sm">
              {locale === "EN" ? "No evidence available" : "Không có bằng chứng"}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function EvidenceContent({ evidence, locale }: { evidence: SignalEvidence; locale: "VN" | "EN" }) {
  return (
    <div className="space-y-5">
      {/* Target summary block */}
      <div className="rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-4 space-y-3">
        <div className="text-xs font-bold uppercase tracking-wider text-[var(--terminal-accent)]">
          {locale === "EN" ? "Signal derivation" : "Nguồn tạo signal"}
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs font-mono">
          <div className="text-[var(--muted)]">
            State: <span className="text-[var(--foreground)] font-bold">{evidence.entry_state || "—"}</span>
          </div>
          <div className="text-[var(--muted)]">
            Time: <span className="text-[var(--foreground)]">{evidence.entry_time || "—"}</span>
          </div>
          <div className="text-[var(--muted)]">
            Rule: <span className="text-[var(--foreground)]">{evidence.entry_rule || "—"}</span>
          </div>
          <div className="text-[var(--muted)]">
            Branch: <span className="text-[var(--foreground)]">{evidence.entry_branch || "—"}</span>
          </div>
          <div className="text-[var(--muted)]">
            Group: <span className="text-[var(--foreground)] font-bold">{evidence.group || "—"}</span>
          </div>
          <div className="text-[var(--muted)]">
            Base: <span className="text-[var(--foreground)]">{evidence.signal_base || "—"}</span>
          </div>
          <div className="text-[var(--muted)]">
            Final: <span className="text-[var(--foreground)] font-bold">{evidence.direction || "WAIT"}</span>
          </div>
          <div className="text-[var(--muted)]">
            Action: <span className="text-[var(--foreground)]">{evidence.entry_action || "—"}</span>
          </div>
        </div>
        {evidence.reused_monday && (
          <div className="rounded border border-[var(--terminal-warning)]/35 bg-[var(--terminal-warning)]/10 px-2.5 py-2 text-xs font-semibold text-[var(--terminal-warning)]">
            {locale === "EN" ? "Thursday reuses Monday" : "Thứ Năm dùng lại Thứ Hai"}: {evidence.reused_monday}
          </div>
        )}
      </div>

      {/* H1 Chart Block */}
      <div className="rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-4 space-y-3">
        <div className="text-xs font-bold uppercase tracking-wider text-[var(--terminal-accent)]">
          {locale === "EN" ? "H1 candle sequence" : "Chuỗi nến H1"}
        </div>
        
        {evidence.candles && evidence.candles.length > 0 ? (
          <MultiCandleSvg candles={evidence.candles} locale={locale} />
        ) : (
          <div className="text-sm text-[var(--terminal-warning)] italic">
            {locale === "EN" ? "No candle data available." : "Không có dữ liệu nến."}
          </div>
        )}
      </div>
    </div>
  );
}

function MultiCandleSvg({ candles, locale }: { candles: EvidenceCandle[]; locale: "VN" | "EN" }) {
  const width = 440;
  const height = 240;
  const padding = { top: 30, right: 30, bottom: 40, left: 30 };
  const chartH = height - padding.top - padding.bottom;

  // Find min/max across all ready candles
  const readyCandles = candles.filter((c) => c.state === "READY" && c.high !== null && c.low !== null);
  
  if (readyCandles.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 border border-dashed border-[var(--panel-border)] rounded text-sm text-[var(--muted)] italic">
        {locale === "EN" ? "Pending candles..." : "Đang chờ dữ liệu nến..."}
      </div>
    );
  }

  const allPrices = readyCandles.flatMap(c => [c.high!, c.low!]);
  const minPrice = Math.min(...allPrices);
  const maxPrice = Math.max(...allPrices);
  const priceRange = maxPrice - minPrice || 1;
  const pricePad = priceRange * 0.15;
  const yMin = minPrice - pricePad;
  const yMax = maxPrice + pricePad;
  const yRange = yMax - yMin;

  const toY = (price: number) => padding.top + chartH * (1 - (price - yMin) / yRange);
  const slotW = (width - padding.left - padding.right) / candles.length;
  const candleWidth = Math.min(24, slotW * 0.6);

  const formatTime = (isoString: string) => {
    const match = /T(\d{2}:\d{2})/.exec(isoString);
    return match?.[1] || isoString;
  };

  return (
    <div className="w-full overflow-x-auto pb-2">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full min-w-[320px] max-w-[500px]" role="img" aria-label={locale === "EN" ? "H1 candle sequence" : "Chuỗi nến H1"}>
        {/* Horizontal Grid lines */}
        {[0, 0.25, 0.5, 0.75, 1].map((frac, i) => {
          const p = yMin + yRange * frac;
          return <line key={i} x1={padding.left} y1={toY(p)} x2={width - padding.right} y2={toY(p)} stroke="var(--panel-border)" strokeWidth={0.5} strokeDasharray={frac === 0 || frac === 1 ? "" : "4 4"} />;
        })}

        {/* Draw candles */}
        {candles.map((c, i) => {
          const cx = padding.left + i * slotW + slotW / 2;
          const isHighlight = c.role.includes("BASE");
          const opacity = isHighlight ? 1 : 0.72;
          
          if (c.state === "PENDING" || c.state === "MISSING") {
            // Draw placeholder box
            return (
              <g key={i} opacity={opacity}>
                <rect x={cx - candleWidth/2} y={padding.top + chartH/2 - 20} width={candleWidth} height={40} fill="transparent" stroke="var(--muted)" strokeDasharray="2 2" />
                <text x={cx} y={padding.top + chartH/2 + 3} textAnchor="middle" fill="var(--muted)" fontSize={10} fontFamily="monospace">{c.state}</text>
                <text x={cx} y={height - padding.bottom + 16} textAnchor="middle" fill="var(--muted)" fontSize={9} fontFamily="monospace">{formatTime(c.open_time)}</text>
                <text x={cx} y={padding.top - 10} textAnchor="middle" fill="var(--muted)" fontSize={10} fontFamily="monospace" fontWeight="bold">{c.role}</text>
              </g>
            );
          }

          const isBuy = c.direction === "BUY";
          const isDoji = c.direction === "DOJI";
          const color = isDoji ? "var(--terminal-warning)" : isBuy ? "var(--terminal-accent)" : "var(--terminal-danger)";
          
          const o = toY(c.open!);
          const h = toY(c.high!);
          const l = toY(c.low!);
          const cl = toY(c.close!);
          const bodyTop = Math.min(o, cl);
          const bodyBottom = Math.max(o, cl);
          const bodyH = Math.max(bodyBottom - bodyTop, 1);

          return (
            <g key={i} opacity={opacity}>
              {/* Role label */}
              <text x={cx} y={padding.top - 10} textAnchor="middle" fill={isHighlight ? "var(--foreground)" : "var(--muted)"} fontSize={10} fontFamily="monospace" fontWeight="bold">{c.role}</text>
              
              {/* Wick */}
              <line x1={cx} y1={h} x2={cx} y2={l} stroke={color} strokeWidth={1.5} />
              
              {/* Body */}
              <rect
                x={cx - candleWidth / 2}
                y={bodyTop}
                width={candleWidth}
                height={bodyH}
                fill={isDoji ? "none" : color}
                stroke={color}
                strokeWidth={1.5}
                opacity={isDoji ? 0.6 : 1.0}
              />
              
              {/* DOJI marker */}
              {isDoji && (
                <text x={cx} y={bodyTop - 6} textAnchor="middle" fill="var(--terminal-warning)" fontSize={8} fontFamily="monospace">DOJI</text>
              )}
              
              {/* Time label */}
              <text x={cx} y={height - padding.bottom + 16} textAnchor="middle" fill="var(--muted)" fontSize={9} fontFamily="monospace">
                {formatTime(c.open_time)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
