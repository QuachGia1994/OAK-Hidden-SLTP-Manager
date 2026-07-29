"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { PairEvidence, SignalEvidence, CandleEvidence, PairDerivation, H1CandleEvidence } from "@/lib/types";
import { useLocale } from "./LocaleProvider";

interface SignalEvidenceDrawerProps {
  evidence: SignalEvidence | null;
  loading: boolean;
  error: string | null;
  open: boolean;
  onClose: () => void;
  date: string;
  hour: number;
}

export function SignalEvidenceDrawer({
  evidence,
  loading,
  error,
  open,
  onClose,
  date,
  hour,
}: SignalEvidenceDrawerProps) {
  const { locale } = useLocale();
  const drawerRef = useRef<HTMLDivElement>(null);
  const [selectedSymbol, setSelectedSymbol] = useState<string | null>(null);

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

  // Select first available symbol when evidence loads
  useEffect(() => {
    if (evidence && !selectedSymbol) {
      const symbols = Object.keys(evidence);
      if (symbols.length > 0) setSelectedSymbol(symbols[0]);
    }
  }, [evidence, selectedSymbol]);

  const symbols = evidence ? Object.keys(evidence) : [];
  const currentPair = evidence && selectedSymbol ? evidence[selectedSymbol] : null;

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
            <div className="text-xs font-bold uppercase tracking-wider text-[var(--terminal-accent)]">
              {locale === "EN" ? "Signal Evidence" : "Bằng chứng Signal"}
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

        {/* Symbol tabs */}
        {symbols.length > 1 && (
          <div className="flex gap-1 px-4 py-2 border-b border-[var(--panel-border)] bg-[var(--surface)]">
            {symbols.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setSelectedSymbol(s)}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition-colors ${
                  s === selectedSymbol
                    ? "bg-[var(--terminal-accent)]/15 text-[var(--terminal-accent)] border border-[var(--terminal-accent)]/30"
                    : "text-[var(--muted)] hover:text-[var(--foreground)] hover:bg-[var(--surface-raised)]"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        )}

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
          {currentPair && (
            <PairEvidenceContent pair={currentPair} symbol={selectedSymbol || ""} locale={locale} />
          )}
          {!loading && !error && !currentPair && (
            <div className="text-center py-12 text-[var(--muted)] text-sm">
              {locale === "EN" ? "No evidence available" : "Không có bằng chứng"}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PairEvidenceContent({ pair, symbol, locale }: { pair: PairEvidence; symbol: string; locale: "VN" | "EN" }) {
  const isGBPAUD = symbol === "GBPAUD";
  const isXAUUSD = symbol === "XAUUSD";

  return (
    <div className="space-y-5">
      {/* Derivation info */}
      {pair.derivation && <DerivationBlock derivation={pair.derivation} symbol={symbol} locale={locale} />}

      {/* GBPAUD H1 evidence — Section A: Final direction source */}
      {isGBPAUD && pair.h1_evidence && (
        <H1CandleSection h1={pair.h1_evidence} locale={locale} />
      )}

      {/* GBPAUD M15 entry timing — Section B (only offset-15) */}
      {isGBPAUD && pair.analysis && pair.analysis.some((c) => c !== null) && (
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-[var(--muted)] mb-2">
            {locale === "EN" ? "XAU Entry Timing (M15 offset -15)" : "XAU Entry Timing (M15 offset -15)"}
          </div>
          <CandleEvidenceChart candles={pair.analysis} locale={locale} />
          <CandleOhlcTable candles={pair.analysis} locale={locale} />
        </div>
      )}

      {/* XAUUSD: show H1 direction source reference */}
      {isXAUUSD && pair.derivation?.type === "XAUUSD_FROM_GBPAUD_H1" && (
        <XAUEntryTimingSection derivation={pair.derivation} locale={locale} />
      )}

      {/* GBPUSD: M15 candle chart */}
      {!isGBPAUD && !isXAUUSD && pair.analysis && pair.analysis.some((c) => c !== null) && (
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-[var(--muted)] mb-2">
            {locale === "EN" ? "Candlestick Chart" : "Biểu đồ nến"}
          </div>
          <CandleEvidenceChart candles={pair.analysis} locale={locale} />
        </div>
      )}

      {/* GBPUSD: OHLC table */}
      {!isGBPAUD && !isXAUUSD && pair.analysis && pair.analysis.some((c) => c !== null) && (
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-[var(--muted)] mb-2">
            {locale === "EN" ? "OHLC Data" : "Dữ liệu OHLC"}
          </div>
          <CandleOhlcTable candles={pair.analysis} locale={locale} />
        </div>
      )}

      {/* Signal path */}
      {pair.evaluation && (
        <div>
          <div className="text-xs font-bold uppercase tracking-wider text-[var(--muted)] mb-2">
            {locale === "EN" ? "Signal Derivation" : "Quy trình suy luận"}
          </div>
          <SignalPath evaluation={pair.evaluation as Record<string, unknown>} symbol={symbol} locale={locale} />
        </div>
      )}
    </div>
  );
}

function DerivationBlock({ derivation, symbol, locale }: { derivation: PairDerivation; symbol: string; locale: "VN" | "EN" }) {
  if (derivation.type === "DEFERRED_TO_H7") {
    return (
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm">
        <span className="font-bold text-amber-400">
          {locale === "EN" ? "Deferred to H7" : "Hoãn đến H7"}
        </span>
        <span className="text-[var(--muted)] ml-2">
          {derivation.reason || (locale === "EN" ? "GBPUSD starts at H7" : "GBPUSD bắt đầu từ H7")}
        </span>
      </div>
    );
  }
  if (derivation.type === "XAUUSD_FROM_GBPAUD_H1") {
    const h1Label = derivation.h1_source_hour != null
      ? `H${derivation.h1_source_hour}`
      : (locale === "EN" ? "previous H1" : "H1 trước");
    return (
      <div className="rounded-lg border border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/10 px-4 py-3 text-sm">
        <div className="font-bold text-[var(--terminal-accent)]">
          {locale === "EN" ? "Final direction source: GBPAUD H1" : "Nguồn direction cuối: GBPAUD H1"}
        </div>
        <div className="text-[var(--muted)] mt-1">
          {locale === "EN"
            ? `XAUUSD direction derived from GBPAUD H1 ${h1Label} (${derivation.source_direction})`
            : `XAUUSD direction lấy từ GBPAUD H1 ${h1Label} (${derivation.source_direction})`}
        </div>
      </div>
    );
  }
  if (derivation.type === "XAUUSD_ENTRY_TIMING") {
    return (
      <div className="rounded-lg border border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/10 px-4 py-3 text-sm">
        <div className="font-bold text-[var(--terminal-accent)]">
          {locale === "EN" ? "XAU Entry Timing" : "XAU Entry Timing"}
        </div>
        <div className="text-[var(--muted)] mt-1">
          {locale === "EN"
            ? `M15 offset -15 direction: ${derivation.offset15_direction || "—"} → ${derivation.entry_relation || "—"} relation`
            : `M15 offset -15 hướng: ${derivation.offset15_direction || "—"} → quan hệ ${derivation.entry_relation || "—"}`}
        </div>
      </div>
    );
  }
  if (derivation.type === "GBPUSD_H9PLUS_INVERSION") {
    return (
      <div className="rounded-lg border border-[var(--terminal-warning)]/30 bg-[var(--terminal-warning)]/10 px-4 py-3 text-sm">
        <div className="font-bold text-[var(--terminal-warning)]">
          {locale === "EN" ? "H9+ inversion applied" : "Đảo chiều H9+ áp dụng"}
        </div>
        <div className="text-[var(--muted)] mt-1">
          {locale === "EN"
            ? `GBPUSD inverted: ${derivation.original_direction} → reversed`
            : `GBPUSD bị đảo: ${derivation.original_direction} → đảo chiều`}
        </div>
      </div>
    );
  }
  return null;
}

// =====================================================================
// H1 Candle Section (GBPAUD Final Direction Source)
// =====================================================================

function H1CandleSection({ h1, locale }: { h1: H1CandleEvidence; locale: "VN" | "EN" }) {
  const isBuy = h1.resolved_direction === "BUY";
  const isDoji = h1.is_doji;

  return (
    <div className="rounded-lg border border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/5 px-4 py-4 space-y-3">
      <div className="text-xs font-bold uppercase tracking-wider text-[var(--terminal-accent)]">
        {locale === "EN" ? "Section A: Final Direction Source" : "Phần A: Nguồn Direction Cuối"}
      </div>
      <div className="text-xs text-[var(--muted)]">
        {locale === "EN"
          ? `H1 candle H${h1.source_hour} → signal slot H${h1.target_hour}`
          : `Nến H1 H${h1.source_hour} → mốc signal H${h1.target_hour}`}
      </div>

      {/* H1 Candle SVG */}
      {h1.candle && (
        <SingleCandleSvg
          candle={h1.candle}
          isBuy={isBuy}
          isDoji={isDoji}
          openTime={h1.candle_open_time}
          closeTime={h1.candle_close_time}
          locale={locale}
        />
      )}

      {/* OHLC */}
      {h1.candle && (
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-mono">
          <div className="text-[var(--muted)]">O <span className="text-[var(--foreground)]">{h1.candle.open.toFixed(h1.candle.open < 1 ? 5 : 2)}</span></div>
          <div className="text-[var(--muted)]">H <span className="text-[var(--foreground)]">{h1.candle.high.toFixed(h1.candle.high < 1 ? 5 : 2)}</span></div>
          <div className="text-[var(--muted)]">L <span className="text-[var(--foreground)]">{h1.candle.low.toFixed(h1.candle.low < 1 ? 5 : 2)}</span></div>
          <div className="text-[var(--muted)]">C <span className="text-[var(--foreground)]">{h1.candle.close.toFixed(h1.candle.close < 1 ? 5 : 2)}</span></div>
        </div>
      )}

      {/* Open / Close times */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-mono">
        <div className="text-[var(--muted)]">
          {locale === "EN" ? "Open" : "Mở"} <span className="text-[var(--foreground)]">{h1.candle_open_time}</span>
        </div>
        <div className="text-[var(--muted)]">
          {locale === "EN" ? "Close" : "Đóng"} <span className="text-[var(--foreground)]">{h1.candle_close_time}</span>
        </div>
      </div>

      {/* Raw / Resolved / Final */}
      <div className="flex items-center gap-3 text-xs font-mono">
        <span className="text-[var(--muted)]">
          {locale === "EN" ? "Raw" : "Thô"}: <span className={isDoji ? "text-[var(--terminal-warning)]" : "text-[var(--foreground)]"}>{h1.raw_direction || "—"}</span>
        </span>
        <span className="text-[var(--muted)]">
          {locale === "EN" ? "Resolved" : "Xác định"}: <span className="text-[var(--foreground)]">{h1.resolved_direction || "—"}</span>
        </span>
        <span className={`font-bold ${isBuy ? "text-[var(--terminal-accent)]" : "text-[var(--terminal-danger)]"}`}>
          {h1.resolved_direction || "—"}
        </span>
      </div>
    </div>
  );
}

// =====================================================================
// Single H1 Candle SVG
// =====================================================================

function SingleCandleSvg({
  candle,
  isBuy,
  isDoji,
  openTime,
  closeTime,
  locale,
}: {
  candle: { open: number; high: number; low: number; close: number };
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
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full max-w-[200px]" role="img" aria-label={locale === "EN" ? "H1 candlestick" : "Nến H1"}>
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

// =====================================================================
// XAU Entry Timing Section (for XAUUSD inspector)
// =====================================================================

function XAUEntryTimingSection({ derivation, locale }: { derivation: PairDerivation; locale: "VN" | "EN" }) {
  const h1Label = derivation.h1_source_hour != null ? `H${derivation.h1_source_hour}` : "H-1";
  const relation = derivation.entry_relation;

  return (
    <div className="rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-4 space-y-3">
      <div className="text-xs font-bold uppercase tracking-wider text-[var(--terminal-accent)]">
        {locale === "EN" ? "Final direction source: GBPAUD H1 H-1" : "Nguồn direction cuối: GBPAUD H1 H-1"}
      </div>
      <div className="text-xs text-[var(--muted)]">
        {locale === "EN"
          ? `GBPAUD H1 ${h1Label} direction: ${derivation.source_direction || "—"}`
          : `GBPAUD H1 ${h1Label} hướng: ${derivation.source_direction || "—"}`}
      </div>
      {relation && (
        <div className="text-xs text-[var(--muted)]">
          {locale === "EN"
            ? `Entry relation: ${relation} (${relation === "SAME" ? ":11/:25" : ":49"})`
            : `Quan hệ entry: ${relation} (${relation === "SAME" ? ":11/:25" : ":49"})`}
        </div>
      )}
      {derivation.offset15_direction && (
        <div className="text-xs text-[var(--muted)]">
          {locale === "EN"
            ? `M15 offset -15 direction: ${derivation.offset15_direction}`
            : `M15 offset -15 hướng: ${derivation.offset15_direction}`}
        </div>
      )}
    </div>
  );
}

// =====================================================================
// SVG Candlestick Chart
// =====================================================================

function CandleEvidenceChart({ candles, locale }: { candles: (CandleEvidence | null)[]; locale: "VN" | "EN" }) {
  const validCandles = candles.filter((c): c is CandleEvidence => c !== null && c.candle !== null);
  if (validCandles.length === 0) return null;

  const width = 420;
  const height = 200;
  const padding = { top: 25, right: 60, bottom: 30, left: 10 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  // Price range
  const allPrices = validCandles.flatMap((c) => [c.candle!.high, c.candle!.low]);
  const minPrice = Math.min(...allPrices);
  const maxPrice = Math.max(...allPrices);
  const priceRange = maxPrice - minPrice || 1;
  const pricePad = priceRange * 0.1;
  const yMin = minPrice - pricePad;
  const yMax = maxPrice + pricePad;
  const yRange = yMax - yMin;

  const toY = (price: number) => padding.top + chartH * (1 - (price - yMin) / yRange);
  const candleSpacing = chartW / validCandles.length;
  const candleWidth = Math.max(candleSpacing * 0.5, 8);

  // Grid lines
  const gridLines = 4;
  const gridPrices = Array.from({ length: gridLines + 1 }, (_, i) => yMin + (yRange * i) / gridLines);

  // Determine significant digits for price labels
  const decimals = priceRange < 0.01 ? 5 : priceRange < 1 ? 3 : 2;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label={locale === "EN" ? "M15 candlestick chart" : "Biểu đồ nến M15"}>
      {/* Grid */}
      {gridPrices.map((p, i) => (
        <line key={i} x1={padding.left} y1={toY(p)} x2={width - padding.right} y2={toY(p)} stroke="var(--panel-border)" strokeWidth={0.5} />
      ))}
      {/* Price labels */}
      {gridPrices.map((p, i) => (
        <text key={i} x={width - padding.right + 4} y={toY(p) + 3} fill="var(--muted)" fontSize={8} fontFamily="monospace">
          {p.toFixed(decimals)}
        </text>
      ))}

      {/* Candles */}
      {validCandles.map((c, i) => {
        const x = padding.left + candleSpacing * i + candleSpacing / 2;
        const isTang = c.resolved_direction === "TANG";
        const isDoji = c.raw_direction === "DOJI";
        const color = isDoji ? "var(--terminal-warning)" : isTang ? "var(--terminal-accent)" : "var(--terminal-danger)";
        const o = toY(c.candle!.open);
        const h = toY(c.candle!.high);
        const l = toY(c.candle!.low);
        const cl = toY(c.candle!.close);
        const bodyTop = Math.min(o, cl);
        const bodyBottom = Math.max(o, cl);
        const bodyH = Math.max(bodyBottom - bodyTop, 1);

        return (
          <g key={i}>
            {/* Wick */}
            <line x1={x} y1={h} x2={x} y2={l} stroke={color} strokeWidth={1} />
            {/* Body */}
            <rect
              x={x - candleWidth / 2}
              y={bodyTop}
              width={candleWidth}
              height={bodyH}
              fill={isDoji ? "none" : color}
              stroke={color}
              strokeWidth={1}
              opacity={isDoji ? 0.6 : 0.85}
            />
            {/* DOJI marker */}
            {isDoji && (
              <text x={x} y={bodyTop - 4} textAnchor="middle" fill="var(--terminal-warning)" fontSize={7} fontFamily="monospace">
                DOJI
              </text>
            )}
            {/* Role label */}
            <text x={x} y={height - padding.bottom + 14} textAnchor="middle" fill="var(--muted)" fontSize={7} fontFamily="monospace">
              {c.role}
            </text>
          </g>
        );
      })}

      {/* Pattern bracket & base accent */}
      {validCandles.length >= 3 && (
        <>
          {/* Pattern bracket (first 3 candles) */}
          <line
            x1={padding.left + candleSpacing * 0.5}
            y1={padding.top - 8}
            x2={padding.left + candleSpacing * 2.5}
            y2={padding.top - 8}
            stroke="var(--terminal-accent)"
            strokeWidth={1}
            opacity={0.5}
          />
          <text
            x={padding.left + candleSpacing * 1.5}
            y={padding.top - 12}
            textAnchor="middle"
            fill="var(--terminal-accent)"
            fontSize={7}
            fontFamily="monospace"
            opacity={0.7}
          >
            {locale === "EN" ? "Pattern" : "Pattern"}
          </text>
        </>
      )}

      {/* Post-filter divider */}
      {validCandles.length >= 5 && (
        <line
          x1={padding.left + candleSpacing * 3.75}
          y1={padding.top}
          x2={padding.left + candleSpacing * 3.75}
          y2={height - padding.bottom}
          stroke="var(--panel-border)"
          strokeWidth={1}
          strokeDasharray="3,3"
          opacity={0.6}
        />
      )}
    </svg>
  );
}

// =====================================================================
// OHLC Table
// =====================================================================

function CandleOhlcTable({ candles, locale }: { candles: (CandleEvidence | null)[]; locale: "VN" | "EN" }) {
  const validCandles = candles.filter((c): c is CandleEvidence => c !== null);
  if (validCandles.length === 0) return null;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="text-[var(--muted)] border-b border-[var(--panel-border)]">
            <th className="text-left py-1 pr-2">{locale === "EN" ? "Role" : "Vai trò"}</th>
            <th className="text-right py-1 px-1">O</th>
            <th className="text-right py-1 px-1">H</th>
            <th className="text-right py-1 px-1">L</th>
            <th className="text-right py-1 px-1">C</th>
            <th className="text-center py-1 px-1">{locale === "EN" ? "Dir" : "Hướng"}</th>
          </tr>
        </thead>
        <tbody>
          {validCandles.map((c, i) => (
            <tr key={i} className="border-b border-[var(--panel-border)]/50">
              <td className="py-1 pr-2 text-[var(--muted)]">{c.role}</td>
              {c.candle ? (
                <>
                  <td className="text-right py-1 px-1">{c.candle.open.toFixed(c.candle.open < 1 ? 5 : 2)}</td>
                  <td className="text-right py-1 px-1">{c.candle.high.toFixed(c.candle.high < 1 ? 5 : 2)}</td>
                  <td className="text-right py-1 px-1">{c.candle.low.toFixed(c.candle.low < 1 ? 5 : 2)}</td>
                  <td className="text-right py-1 px-1">{c.candle.close.toFixed(c.candle.close < 1 ? 5 : 2)}</td>
                </>
              ) : (
                <td colSpan={4} className="text-center py-1 text-[var(--muted)]">—</td>
              )}
              <td className="text-center py-1 px-1">
                {c.raw_direction === "DOJI" ? (
                  <span className="text-[var(--terminal-warning)]">
                    DOJI→{c.resolved_direction || "?"}
                  </span>
                ) : c.resolved_direction === "TANG" ? (
                  <span className="text-[var(--terminal-accent)]">TANG</span>
                ) : c.resolved_direction === "GIAM" ? (
                  <span className="text-[var(--terminal-danger)]">GIAM</span>
                ) : (
                  <span className="text-[var(--muted)]">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// =====================================================================
// Signal Derivation Path
// =====================================================================

function SignalPath({ evaluation, symbol, locale }: { evaluation: Record<string, unknown>; symbol: string; locale: "VN" | "EN" }) {
  const steps: { label: string; value: string }[] = [];

  const baseDir = evaluation.base_direction as string | undefined;
  if (baseDir) {
    steps.push({
      label: locale === "EN" ? "Base (-30)" : "Base (-30)",
      value: baseDir,
    });
  }

  const group = evaluation.pullback_group as string | undefined;
  if (group) {
    steps.push({
      label: locale === "EN" ? "Pattern" : "Pattern",
      value: group,
    });
  }

  const preOffset15 = evaluation.pre_offset15_direction as string | undefined;
  if (preOffset15) {
    steps.push({
      label: locale === "EN" ? "Pre-filter" : "Trước lọc",
      value: preOffset15,
    });
  }

  const offset15Dir = evaluation.offset15_direction as string | undefined;
  const offset15Relation = evaluation.offset15_relation as string | undefined;
  const offset15Action = evaluation.offset15_action as string | undefined;
  if (offset15Dir) {
    steps.push({
      label: locale === "EN" ? "Post-filter (-15)" : "Hậu kiểm (-15)",
      value: `${offset15Dir} ${offset15Relation ? `(${offset15Relation} → ${offset15Action})` : ""}`,
    });
  }

  const postOffset15 = evaluation.post_offset15_direction as string | undefined;
  if (postOffset15) {
    steps.push({
      label: locale === "EN" ? "Post-filter result" : "Kết quả hậu kiểm",
      value: postOffset15,
    });
  }

  // GBPUSD inversion
  const inverted = evaluation.gbpusd_h9plus_inversion_applied as boolean | undefined;
  if (inverted) {
    steps.push({
      label: locale === "EN" ? "H9+ inversion" : "Đảo chiều H9+",
      value: locale === "EN" ? "Applied" : "Áp dụng",
    });
  }

  const finalDir = evaluation.direction as string | undefined;
  if (finalDir) {
    steps.push({
      label: locale === "EN" ? "Final direction" : "Hướng cuối",
      value: finalDir,
    });
  }

  if (steps.length === 0) return null;

  return (
    <div className="space-y-1.5">
      {steps.map((step, i) => (
        <div key={i} className="flex items-center justify-between text-xs">
          <span className="text-[var(--muted)]">{step.label}</span>
          <span className={`font-mono font-bold ${
            step.value === "TANG" || step.value === "BUY"
              ? "text-[var(--terminal-accent)]"
              : step.value === "GIAM" || step.value === "SELL"
              ? "text-[var(--terminal-danger)]"
              : step.value === "SW"
              ? "text-[var(--terminal-warning)]"
              : "text-[var(--foreground)]"
          }`}>
            {step.value}
          </span>
        </div>
      ))}
      {/* Arrow connector */}
      <div className="flex items-center justify-center py-1">
        <svg className="w-4 h-4 text-[var(--terminal-accent)]" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 13.5L12 21m0 0l-7.5-7.5M12 21V3" />
        </svg>
      </div>
    </div>
  );
}
