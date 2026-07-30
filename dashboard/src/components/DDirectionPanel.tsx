"use client";

import { useMemo } from "react";
import type { DDirectionEvidence } from "@/lib/types";

interface DDirectionPanelProps {
  dailyDirections?: Record<string, unknown> | null;
  dDirections?: Record<string, unknown> | null;
  locale: "VN" | "EN";
}

const ALL_SYMBOLS = ["XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD"] as const;
const ACTIVE_EXECUTION_SYMBOLS = new Set(["XAUUSD", "GBPUSD", "GBPAUD"]);

export function DDirectionPanel({ dailyDirections, dDirections, locale }: DDirectionPanelProps) {
  const directionsMap = useMemo(() => {
    const map = (dailyDirections || dDirections || {}) as Record<string, DDirectionEvidence>;
    return map;
  }, [dailyDirections, dDirections]);

  return (
    <section className="terminal-panel rounded-2xl p-5 sm:p-6 space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="terminal-kicker text-[var(--terminal-accent)]">
            {locale === "EN" ? "Daily Anchor" : "Mốc phiên Daily"}
          </div>
          <h2 className="font-mono text-sm font-bold uppercase tracking-[0.2em] text-[var(--foreground)]">
            D-DIRECTION (SESSION M30)
          </h2>
        </div>
        <span className="rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-2.5 py-1 font-mono text-[10px] font-bold text-[var(--muted)]">
          5 SYMBOLS
        </span>
      </div>

      <div className="divide-y divide-[var(--panel-border)] rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)]/40 overflow-hidden">
        {ALL_SYMBOLS.map((symbol) => {
          const info = directionsMap[symbol] as DDirectionEvidence | undefined;
          const dDir = info?.d_direction || "MISSING";
          const isExecutionOn = ACTIVE_EXECUTION_SYMBOLS.has(symbol);
          const sessionDate = info?.session_date || info?.target_date || "—";
          const openTime = info?.d_candle_open_time
            ? /T(\d{2}:\d{2})/.exec(info.d_candle_open_time)?.[1] || "23:30"
            : "—";
          const candle = info?.candle;

          return (
            <div
              key={symbol}
              className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:justify-between text-xs font-mono"
            >
              {/* Left: Symbol & Badges */}
              <div className="flex items-center gap-2.5 min-w-[180px]">
                <span className="font-black text-[var(--foreground)] text-sm">{symbol}</span>
                <span
                  className={`rounded px-1.5 py-0.5 text-[9px] font-bold uppercase ${
                    isExecutionOn
                      ? "bg-[var(--terminal-accent)]/15 text-[var(--terminal-accent)]"
                      : "bg-[var(--terminal-warning)]/15 text-[var(--terminal-warning)]"
                  }`}
                >
                  {isExecutionOn ? "EXEC ON" : "EXEC OFF"}
                </span>
                <DirectionBadge dir={dDir} />
              </div>

              {/* Middle: Session & M30 timing */}
              <div className="flex items-center gap-3 text-[var(--muted)] text-[11px]">
                <div>
                  <span className="text-[var(--muted)]/60">Session: </span>
                  <span className="text-[var(--foreground)] font-semibold">{sessionDate}</span>
                </div>
                <div>
                  <span className="text-[var(--muted)]/60">M30: </span>
                  <span className="text-[var(--foreground)] font-semibold">
                    {openTime !== "—" ? `${openTime} → 00:00` : "—"}
                  </span>
                </div>
              </div>

              {/* Right: OHLC & Mini Candle SVG */}
              <div className="flex items-center justify-between sm:justify-end gap-3 text-[11px]">
                {candle ? (
                  <div className="flex items-center gap-2 text-[var(--muted)]">
                    <span>O:{formatPrice(candle.open)}</span>
                    <span>H:{formatPrice(candle.high)}</span>
                    <span>L:{formatPrice(candle.low)}</span>
                    <span className="text-[var(--foreground)] font-bold">C:{formatPrice(candle.close)}</span>
                  </div>
                ) : (
                  <span className="text-[var(--muted)] italic">No candle data</span>
                )}
                <MiniCandleSvg candle={candle} direction={dDir} />
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function DirectionBadge({ dir }: { dir: string }) {
  let style = "bg-[var(--surface)] text-[var(--muted)] border-[var(--panel-border)]";
  if (dir === "BUY") style = "bg-[var(--terminal-accent)]/20 text-[var(--terminal-accent)] border-[var(--terminal-accent)]/40";
  if (dir === "SELL") style = "bg-[var(--terminal-danger)]/20 text-[var(--terminal-danger)] border-[var(--terminal-danger)]/40";
  if (dir === "DOJI") style = "bg-[var(--terminal-warning)]/20 text-[var(--terminal-warning)] border-[var(--terminal-warning)]/40";

  return (
    <span className={`rounded border px-2 py-0.5 text-[10px] font-black tracking-wider ${style}`}>
      {dir}
    </span>
  );
}

function MiniCandleSvg({
  candle,
  direction,
}: {
  candle?: { open: number | null; high: number | null; low: number | null; close: number | null } | null;
  direction: string;
}) {
  if (!candle || candle.open === null || candle.close === null || candle.high === null || candle.low === null) {
    return (
      <svg width="18" height="28" viewBox="0 0 18 28" className="opacity-40">
        <rect x="5" y="6" width="8" height="16" fill="none" stroke="var(--muted)" strokeDasharray="2 2" />
      </svg>
    );
  }

  const isUp = candle.close >= candle.open;
  const isDoji = direction === "DOJI" || Math.abs(candle.close - candle.open) < 0.0001;
  const strokeColor = isDoji
    ? "var(--terminal-warning)"
    : isUp
    ? "var(--terminal-accent)"
    : "var(--terminal-danger)";

  const high = candle.high;
  const low = candle.low;
  const range = high - low || 1;

  const toY = (val: number) => 3 + (1 - (val - low) / range) * 22;

  const openY = toY(candle.open);
  const closeY = toY(candle.close);
  const bodyTop = Math.min(openY, closeY);
  const bodyHeight = Math.max(Math.abs(closeY - openY), 2);

  return (
    <svg width="18" height="28" viewBox="0 0 18 28">
      <line x1="9" y1={toY(high)} x2="9" y2={toY(low)} stroke={strokeColor} strokeWidth="1.5" />
      <rect
        x="4"
        y={bodyTop}
        width="10"
        height={bodyHeight}
        fill={isDoji ? "none" : strokeColor}
        stroke={strokeColor}
        strokeWidth="1.5"
      />
    </svg>
  );
}

function formatPrice(value: number | null): string {
  if (value === null || value === undefined) return "—";
  return Number(value).toFixed(2);
}
