"use client";

import { useEffect, useRef } from "react";
import type { SignalEvidence, CandleOhlc } from "@/lib/types";
import { useLocale } from "./LocaleProvider";
import { getSignalLabel } from "@/lib/constants";

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
                {locale === "EN" ? "Evidence v" : "Bằng chứng v"}{evidence?.logic_version || "69"}
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
  const isDoji = evidence.base_signal === "DOJI";
  const missingBase = !evidence.base_candle;
  
  return (
    <div className="space-y-5">
      {/* Entry Branch Selection */}
      <div className="rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-4 space-y-3">
        <div className="text-xs font-bold uppercase tracking-wider text-[var(--terminal-accent)]">
          {locale === "EN" ? "1. Entry Branch Selection" : "1. Chọn nhánh theo Entry"}
        </div>
        <div className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs font-mono">
          <div className="text-[var(--muted)]">
            XAU Entry: <span className="text-[var(--foreground)]">{evidence.xau_entry_time || "—"}</span>
          </div>
          <div className="text-[var(--muted)]">
            Branch: <span className="text-[var(--foreground)]">{evidence.entry_branch || "—"}</span>
          </div>
          <div className="text-[var(--muted)]">
            Base Offset: <span className="text-[var(--foreground)]">-{Math.abs(evidence.base_open_offset_minutes)}m to {evidence.base_close_offset_minutes === 0 ? "0m" : `-${Math.abs(evidence.base_close_offset_minutes)}m`}</span>
          </div>
        </div>
      </div>

      {/* The Base Candle */}
      <div className={`rounded-lg border px-4 py-4 space-y-3 ${
        missingBase || isDoji 
          ? "border-[var(--terminal-warning)]/30 bg-[var(--terminal-warning)]/5" 
          : "border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/5"
      }`}>
        <div className={`text-xs font-bold uppercase tracking-wider ${
          missingBase || isDoji ? "text-[var(--terminal-warning)]" : "text-[var(--terminal-accent)]"
        }`}>
          {locale === "EN" ? "2. The M15 Base Candle" : "2. Nến Base M15"}
        </div>
        
        {missingBase ? (
          <div className="text-sm text-[var(--terminal-warning)] italic">
            {locale === "EN" ? "Missing candle data." : "Không lấy được dữ liệu nến."}
          </div>
        ) : (
          <>
            <SingleCandleSvg
              candle={evidence.base_candle!}
              isBuy={evidence.base_direction === "BUY" || evidence.base_direction === "TANG"}
              isDoji={isDoji}
              openTime={evidence.base_open_time}
              closeTime={evidence.base_close_time}
              locale={locale}
            />
            
            {/* OHLC */}
            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-mono">
              <div className="text-[var(--muted)]">O <span className="text-[var(--foreground)]">{evidence.base_candle!.open.toFixed(evidence.base_candle!.open < 1 ? 5 : 2)}</span></div>
              <div className="text-[var(--muted)]">H <span className="text-[var(--foreground)]">{evidence.base_candle!.high.toFixed(evidence.base_candle!.high < 1 ? 5 : 2)}</span></div>
              <div className="text-[var(--muted)]">L <span className="text-[var(--foreground)]">{evidence.base_candle!.low.toFixed(evidence.base_candle!.low < 1 ? 5 : 2)}</span></div>
              <div className="text-[var(--muted)]">C <span className="text-[var(--foreground)]">{evidence.base_candle!.close.toFixed(evidence.base_candle!.close < 1 ? 5 : 2)}</span></div>
            </div>
            
            <div className="flex items-center gap-3 text-xs font-mono">
              <span className="text-[var(--muted)]">
                Base Signal: <span className={isDoji ? "text-[var(--terminal-warning)]" : "text-[var(--foreground)]"}>{evidence.base_signal || "—"}</span>
              </span>
            </div>
          </>
        )}
      </div>

      {/* Signal Derivation */}
      <div className="rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-4 space-y-3">
        <div className="text-xs font-bold uppercase tracking-wider text-[var(--terminal-accent)]">
          {locale === "EN" ? "3. Final Derivation" : "3. Suy luận kết quả"}
        </div>
        
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="text-[var(--muted)]">{locale === "EN" ? "Primary Rule (Entry)" : "Luật Primary (từ nhánh)"}</span>
            <span className="font-mono font-bold text-[var(--foreground)]">{evidence.primary_action || "—"}</span>
          </div>
          
          <div className="flex items-center justify-between text-xs">
            <span className="text-[var(--muted)]">{locale === "EN" ? "Primary Direction" : "Hướng Primary"}</span>
            <span className={`font-mono font-bold ${
              evidence.primary_direction === "BUY" ? "text-[var(--terminal-accent)]" :
              evidence.primary_direction === "SELL" ? "text-[var(--terminal-danger)]" :
              "text-[var(--foreground)]"
            }`}>{evidence.primary_direction || "—"}</span>
          </div>

          <div className="flex items-center justify-center py-1">
            <svg className="w-4 h-4 text-[var(--terminal-accent)]" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 13.5L12 21m0 0l-7.5-7.5M12 21V3" />
            </svg>
          </div>

          {evidence.slot_inversion_applied && (
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="text-[var(--muted)]">{locale === "EN" ? "Slot Inversion (H14/H16)" : "Đảo chiều theo Mốc (H14/H16)"}</span>
              <span className="font-mono font-bold text-[var(--terminal-warning)]">APPLIED</span>
            </div>
          )}
          
          <div className="flex items-center justify-between text-xs pt-2 border-t border-[var(--panel-border)]">
            <span className="text-[var(--muted)] font-bold">{locale === "EN" ? "Final Direction" : "Kết luận (Final)"}</span>
            <span className={`font-mono font-bold px-2 py-0.5 rounded ${
              evidence.direction === "BUY" ? "bg-[var(--terminal-accent)]/20 text-[var(--terminal-accent)]" : 
              evidence.direction === "SELL" ? "bg-[var(--terminal-danger)]/20 text-[var(--terminal-danger)]" : 
              "bg-[var(--surface)] text-[var(--muted)]"
            }`}>
              {evidence.direction || "WAIT"}
            </span>
          </div>
          
          <div className="flex items-center justify-between text-[10px] mt-1">
            <span className="text-[var(--muted)]">{locale === "EN" ? "Reason" : "Lý do"}</span>
            <span className="font-mono text-[var(--muted)]">{evidence.classification_reason || "—"}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// Single Candle SVG
function SingleCandleSvg({
  candle,
  isBuy,
  isDoji,
  openTime,
  closeTime,
  locale,
}: {
  candle: CandleOhlc;
  isBuy: boolean;
  isDoji: boolean;
  openTime: string;
  closeTime: string;
  locale: "VN" | "EN";
}) {
  const width = 200;
  const height = 160;
  const padding = { top: 20, right: 20, bottom: 30, left: 20 };
  const chartH = height - padding.top - padding.bottom;

  const allPrices = [candle.high, candle.low];
  const minPrice = Math.min(...allPrices);
  const maxPrice = Math.max(...allPrices);
  const priceRange = maxPrice - minPrice || 1;
  const pricePad = priceRange * 0.15;
  const yMin = minPrice - pricePad;
  const yMax = maxPrice + pricePad;
  const yRange = yMax - yMin;

  const toY = (price: number) => padding.top + chartH * (1 - (price - yMin) / yRange);
  const x = width / 2;
  const candleWidth = 40;

  const color = isDoji ? "var(--terminal-warning)" : isBuy ? "var(--terminal-accent)" : "var(--terminal-danger)";
  const o = toY(candle.open);
  const h = toY(candle.high);
  const l = toY(candle.low);
  const cl = toY(candle.close);
  const bodyTop = Math.min(o, cl);
  const bodyBottom = Math.max(o, cl);
  const bodyH = Math.max(bodyBottom - bodyTop, 1);

  const decimals = priceRange < 0.01 ? 5 : priceRange < 1 ? 3 : 2;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full max-w-[200px]" role="img" aria-label={locale === "EN" ? "M15 candlestick" : "Nến M15"}>
      {/* Grid lines */}
      {[0.25, 0.5, 0.75].map((frac, i) => {
        const p = yMin + yRange * frac;
        return <line key={i} x1={padding.left} y1={toY(p)} x2={width - padding.right} y2={toY(p)} stroke="var(--panel-border)" strokeWidth={0.5} />;
      })}
      {/* Wick */}
      <line x1={x} y1={h} x2={x} y2={l} stroke={color} strokeWidth={1.5} />
      {/* Body */}
      <rect
        x={x - candleWidth / 2}
        y={bodyTop}
        width={candleWidth}
        height={bodyH}
        fill={isDoji ? "none" : color}
        stroke={color}
        strokeWidth={1.5}
        opacity={isDoji ? 0.6 : 0.85}
      />
      {/* DOJI marker */}
      {isDoji && (
        <text x={x} y={bodyTop - 6} textAnchor="middle" fill="var(--terminal-warning)" fontSize={8} fontFamily="monospace">
          DOJI
        </text>
      )}
      {/* High label */}
      <text x={width - padding.right + 4} y={h + 3} fill="var(--muted)" fontSize={7} fontFamily="monospace">
        {candle.high.toFixed(decimals)}
      </text>
      {/* Low label */}
      <text x={width - padding.right + 4} y={l + 3} fill="var(--muted)" fontSize={7} fontFamily="monospace">
        {candle.low.toFixed(decimals)}
      </text>
      {/* Time labels */}
      <text x={x} y={height - padding.bottom + 12} textAnchor="middle" fill="var(--muted)" fontSize={7} fontFamily="monospace">
        {openTime}
      </text>
      <text x={x} y={height - padding.bottom + 22} textAnchor="middle" fill="var(--muted)" fontSize={7} fontFamily="monospace">
        → {closeTime}
      </text>
    </svg>
  );
}