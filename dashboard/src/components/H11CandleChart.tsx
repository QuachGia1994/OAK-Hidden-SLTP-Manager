"use client";

import { getH11ChartTitle } from "@/lib/signal-note-i18n";
import type { H11Candle } from "@/lib/types";

interface H11CandleChartProps {
  candles?: H11Candle[];
  locale: "VN" | "EN";
  hour?: number;
}

export function H11CandleChart({ candles, locale, hour }: H11CandleChartProps) {
  if (!candles || candles.length === 0) {
    return null;
  }

  const sortedCandles = [...candles].sort(
    (a, b) => (a.label || "").localeCompare(b.label || "") || a.hour - b.hour,
  );

  const allHighs = sortedCandles.map((c) => c.high);
  const allLows = sortedCandles.map((c) => c.low);
  const maxHigh = Math.max(...allHighs);
  const minLow = Math.min(...allLows);
  const range = maxHigh - minLow || 1;
  const padding = range * 0.12;
  const chartMin = minLow - padding;
  const chartMax = maxHigh + padding;
  const chartRange = chartMax - chartMin;

  const width = 280;
  const height = 120; // extra 10px headroom for DOJI badge
  const candleSlotWidth = width / sortedCandles.length;

  const getY = (price: number) => {
    return height - ((price - chartMin) / chartRange) * (height - 30) - 14;
  };

  const titleText =
    hour === 1500
      ? locale === "EN"
        ? "M30 Candles Chart (13:00-14:30)"
        : "Biểu đồ nến M30 (13:00-14:30)"
      : getH11ChartTitle(locale);

  const hasDoji = sortedCandles.some((c) => c.doji);

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-[11px] font-black uppercase tracking-wider text-[var(--foreground)]">
          {titleText}
        </span>
        <div className="flex items-center gap-2">
          {hasDoji && (
            <span className="rounded-full border border-amber-400/60 bg-amber-400/10 px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-widest text-amber-400">
              {locale === "EN" ? "DOJI fallback" : "Nến DOJI →lùi 1"}
            </span>
          )}
          <span className="font-mono text-[10px] text-[var(--muted)]">
            {minLow.toFixed(2)} - {maxHigh.toFixed(2)}
          </span>
        </div>
      </div>

      <div className="relative w-full overflow-hidden">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto overflow-visible">
          {/* Grid lines */}
          <line x1="0" y1={getY(maxHigh)} x2={width} y2={getY(maxHigh)} stroke="var(--panel-border)" strokeDasharray="3 3" strokeWidth="1" opacity="0.6" />
          <line x1="0" y1={getY(minLow)} x2={width} y2={getY(minLow)} stroke="var(--panel-border)" strokeDasharray="3 3" strokeWidth="1" opacity="0.6" />

          {/* DOJI candle amber glow filter */}
          <defs>
            <filter id="doji-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="2.5" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {sortedCandles.map((c, i) => {
            const isDoji = !!c.doji;
            const isBullish = c.close >= c.open;
            const candleColor = isDoji
              ? "#f59e0b"                                      // amber for DOJI
              : isBullish
              ? "var(--terminal-accent)"
              : "var(--terminal-danger)";
            const fillBg = isDoji
              ? "rgba(245,158,11,0.15)"                       // amber translucent body
              : isBullish
              ? "var(--terminal-accent)"
              : "var(--terminal-danger)";
            const xCenter = i * candleSlotWidth + candleSlotWidth / 2;

            const highY = getY(c.high);
            const lowY = getY(c.low);
            const openY = getY(c.open);
            const closeY = getY(c.close);

            const bodyTop = Math.min(openY, closeY);
            const bodyHeight = Math.max(Math.abs(closeY - openY), isDoji ? 1.5 : 2.5);
            const bodyWidth = 26;
            const bodyX = xCenter - bodyWidth / 2;
            const candleLabel = c.label || `H=${c.hour}`;

            return (
              <g key={c.label || c.hour} className="transition-opacity duration-150 hover:opacity-80">
                {/* Amber glow ring behind body for DOJI */}
                {isDoji && (
                  <rect
                    x={bodyX - 3}
                    y={bodyTop - 3}
                    width={bodyWidth + 6}
                    height={bodyHeight + 6}
                    rx="5"
                    fill="none"
                    stroke="#f59e0b"
                    strokeWidth="1.5"
                    strokeDasharray="3 2"
                    opacity="0.7"
                    filter="url(#doji-glow)"
                  />
                )}

                {/* Wick */}
                <line
                  x1={xCenter}
                  y1={highY}
                  x2={xCenter}
                  y2={lowY}
                  stroke={candleColor}
                  strokeWidth={isDoji ? "1.5" : "1.5"}
                  strokeDasharray={isDoji ? "3 2" : undefined}
                  strokeLinecap="round"
                />

                {/* Body */}
                <rect
                  x={bodyX}
                  y={bodyTop}
                  width={bodyWidth}
                  height={bodyHeight}
                  rx="3"
                  fill={fillBg}
                  stroke={candleColor}
                  strokeWidth={isDoji ? "1.5" : "1"}
                />

                {/* DOJI badge text above candle */}
                {isDoji && (
                  <text
                    x={xCenter}
                    y={highY - 4}
                    textAnchor="middle"
                    fill="#f59e0b"
                    fontSize="7"
                    fontFamily="Consolas, monospace"
                    fontWeight="bold"
                    letterSpacing="0.5"
                  >
                    DOJI
                  </text>
                )}

                {/* Time label */}
                <text
                  x={xCenter}
                  y={height - 1}
                  textAnchor="middle"
                  fill={isDoji ? "#f59e0b" : "var(--muted)"}
                  fontSize="9"
                  fontFamily="Consolas, monospace"
                  fontWeight="bold"
                >
                  {candleLabel}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* Info boxes */}
      <div className="mt-3 grid grid-cols-4 gap-1.5 pt-2 border-t border-[var(--panel-border)]">
        {sortedCandles.map((c) => {
          const isDoji = !!c.doji;
          const isBullish = c.close >= c.open;
          const candleLabel = c.label || `H=${c.hour}`;
          return (
            <div
              key={c.label || c.hour}
              className={`flex flex-col items-center rounded-lg border p-1.5 text-center font-mono text-[10px] ${
                isDoji
                  ? "border-amber-400/50 bg-amber-400/5"
                  : "border-[var(--panel-border)] bg-[var(--surface)]"
              }`}
            >
              <div className="flex items-center gap-1 font-bold text-[var(--foreground)]">
                <span className={isDoji ? "text-amber-400" : ""}>{candleLabel}</span>
                <span
                  className={
                    isDoji
                      ? "text-amber-400"
                      : isBullish
                      ? "text-[var(--terminal-accent)]"
                      : "text-[var(--terminal-danger)]"
                  }
                >
                  {isDoji ? "↕" : isBullish ? "↑" : "↓"}
                </span>
              </div>
              {isDoji && (
                <div className="mb-0.5 text-[8px] font-bold uppercase tracking-wider text-amber-400">
                  doji
                </div>
              )}
              <div className="mt-1 space-y-0.5 text-[9px] leading-tight text-[var(--muted)]">
                <div>O: <span className="text-[var(--foreground)]">{c.open.toFixed(2)}</span></div>
                <div>H: <span className="text-[var(--foreground)]">{c.high.toFixed(2)}</span></div>
                <div>L: <span className="text-[var(--foreground)]">{c.low.toFixed(2)}</span></div>
                <div>C: <span className="text-[var(--foreground)]">{c.close.toFixed(2)}</span></div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
