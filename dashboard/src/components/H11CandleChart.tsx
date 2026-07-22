"use client";

import { getH11ChartTitle } from "@/lib/signal-note-i18n";
import type { H11Candle } from "@/lib/types";

interface H11CandleChartProps {
  candles?: H11Candle[];
  locale: "VN" | "EN";
}

export function H11CandleChart({ candles, locale }: H11CandleChartProps) {
  if (!candles || candles.length === 0) {
    return null;
  }

  const sortedCandles = [...candles].sort((a, b) => a.hour - b.hour);

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
  const height = 110;
  const candleSlotWidth = width / sortedCandles.length;

  const getY = (price: number) => {
    return height - ((price - chartMin) / chartRange) * (height - 24) - 12;
  };

  return (
    <div className="mt-3 overflow-hidden rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="font-mono text-[11px] font-black uppercase tracking-wider text-[var(--foreground)]">
          {getH11ChartTitle(locale)}
        </span>
        <span className="font-mono text-[10px] text-[var(--muted)]">
          {minLow.toFixed(2)} - {maxHigh.toFixed(2)}
        </span>
      </div>

      <div className="relative w-full overflow-hidden">
        <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto overflow-visible">
          <line x1="0" y1={getY(maxHigh)} x2={width} y2={getY(maxHigh)} stroke="var(--panel-border)" strokeDasharray="3 3" strokeWidth="1" opacity="0.6" />
          <line x1="0" y1={getY(minLow)} x2={width} y2={getY(minLow)} stroke="var(--panel-border)" strokeDasharray="3 3" strokeWidth="1" opacity="0.6" />

          {sortedCandles.map((c, i) => {
            const isBullish = c.close >= c.open;
            const candleColor = isBullish ? "var(--terminal-accent)" : "var(--terminal-danger)";
            const fillBg = isBullish ? "var(--terminal-accent)" : "var(--terminal-danger)";
            const xCenter = i * candleSlotWidth + candleSlotWidth / 2;

            const highY = getY(c.high);
            const lowY = getY(c.low);
            const openY = getY(c.open);
            const closeY = getY(c.close);

            const bodyTop = Math.min(openY, closeY);
            const bodyHeight = Math.max(Math.abs(closeY - openY), 2.5);
            const bodyWidth = 26;
            const bodyX = xCenter - bodyWidth / 2;

            return (
              <g key={c.hour} className="transition-opacity duration-150 hover:opacity-80">
                <line
                  x1={xCenter}
                  y1={highY}
                  x2={xCenter}
                  y2={lowY}
                  stroke={candleColor}
                  strokeWidth="1.5"
                  strokeLinecap="round"
                />
                <rect
                  x={bodyX}
                  y={bodyTop}
                  width={bodyWidth}
                  height={bodyHeight}
                  rx="3"
                  fill={fillBg}
                  stroke={candleColor}
                  strokeWidth="1"
                />
                <text
                  x={xCenter}
                  y={height - 2}
                  textAnchor="middle"
                  fill="var(--muted)"
                  fontSize="9"
                  fontFamily="Consolas, monospace"
                  fontWeight="bold"
                >
                  H={c.hour}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <div className="mt-3 grid grid-cols-4 gap-1.5 pt-2 border-t border-[var(--panel-border)]">
        {sortedCandles.map((c) => {
          const isBullish = c.close >= c.open;
          return (
            <div
              key={c.hour}
              className="flex flex-col items-center rounded-lg border border-[var(--panel-border)] bg-[var(--surface)] p-1.5 text-center font-mono text-[10px]"
            >
              <div className="flex items-center gap-1 font-bold text-[var(--foreground)]">
                <span>H={c.hour}</span>
                <span className={isBullish ? "text-[var(--terminal-accent)]" : "text-[var(--terminal-danger)]"}>
                  {isBullish ? "↑" : "↓"}
                </span>
              </div>
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
