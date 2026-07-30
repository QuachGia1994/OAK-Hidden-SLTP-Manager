"use client";

import { useState, useMemo } from "react";
import type { DDirectionSnapshotV2, DDirectionSymbolData } from "@/lib/types";
import { DDirectionDrawer } from "./DDirectionDrawer";

const DISPLAY_SYMBOLS = ["XAUUSD", "GBPUSD", "GBPAUD", "GBPJPY", "GBPCAD"] as const;
const OFF_SYMBOLS = new Set(["GBPJPY", "GBPCAD"]);

const DEFAULT_DIGITS: Record<string, number> = {
  XAUUSD: 2,
  GBPUSD: 5,
  GBPAUD: 5,
  GBPJPY: 3,
  GBPCAD: 5,
};

interface Props {
  snapshot?: DDirectionSnapshotV2 | null;
  date?: string;
  locale: "VN" | "EN";
  className?: string;
}

export function DDirectionPanel({ snapshot, date, locale, className = "" }: Props) {
  const [selectedSymbol, setSelectedSymbol] = useState<DDirectionSymbolData | null>(null);

  const state = snapshot?.state || (snapshot?.message ? "PENDING_PUBLICATION" : "SYNCING");
  const targetDate = snapshot?.target_local_date || date || "—";
  const symbols = snapshot?.symbols || {};

  return (
    <section className={`space-y-3 ${className}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="terminal-section-heading text-xs font-mono font-bold uppercase tracking-[0.22em] text-[var(--muted)]">
            {locale === "EN" ? "D-DIRECTION (SESSION BASE)" : "D-DIRECTION PHIÊN TRƯỚC"}
          </h2>
          <span className="text-[11px] font-mono text-[var(--muted)]">· {targetDate}</span>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`rounded-md px-2.5 py-0.5 font-mono text-[10px] font-bold uppercase tracking-[0.14em] ${
              state === "READY"
                ? "border border-[var(--terminal-accent)]/30 bg-[var(--terminal-accent)]/10 text-[var(--terminal-accent)]"
                : state === "PENDING_PUBLICATION"
                ? "border border-[var(--terminal-warning)]/40 bg-[var(--terminal-warning)]/10 text-[var(--terminal-warning)]"
                : state === "PARTIAL"
                ? "border border-[var(--terminal-warning)]/30 bg-[var(--terminal-warning)]/10 text-[var(--terminal-warning)]"
                : "border border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--muted)]"
            }`}
          >
            {state === "PENDING_PUBLICATION"
              ? locale === "EN"
                ? "Scheduled 06:00 GMT+7"
                : "Chờ công bố 06:00 GMT+7"
              : state === "SYNCING"
              ? locale === "EN"
                ? "Syncing"
                : "Đang nhận"
              : state === "MISSING"
              ? locale === "EN"
                ? "Data Missing"
                : "Thiếu dữ liệu"
              : state}
          </span>
        </div>
      </div>

      {state === "PENDING_PUBLICATION" && (
        <div className="rounded-xl border border-dashed border-[var(--terminal-warning)]/40 bg-[var(--terminal-warning)]/[0.06] p-4 text-xs font-mono text-[var(--terminal-warning)]">
          {locale === "EN"
            ? "D-Direction snapshot is calculated and published independently at 06:00 GMT+7 daily."
            : "D-Direction được tính và công bố độc lập lúc 06:00 GMT+7 mỗi ngày."}
        </div>
      )}

      {state === "SYNCING" && (
        <div className="rounded-xl border border-dashed border-[var(--panel-border)] bg-[var(--surface-raised)]/40 p-4 text-xs font-mono text-[var(--muted)]">
          {locale === "EN" ? "Loading D-Direction snapshot…" : "Đang nhận D-Direction…"}
        </div>
      )}

      {state !== "PENDING_PUBLICATION" && state !== "SYNCING" && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {DISPLAY_SYMBOLS.map((sym) => {
            const data = symbols[sym];
            const isOff = OFF_SYMBOLS.has(sym);
            const digits = data?.price_digits || DEFAULT_DIGITS[sym] || 5;

            return (
              <DDirectionCard
                key={sym}
                symbol={sym}
                data={data}
                isOff={isOff}
                digits={digits}
                locale={locale}
                onClick={() => data && setSelectedSymbol(data)}
              />
            );
          })}
        </div>
      )}

      <DDirectionDrawer
        symbolData={selectedSymbol}
        open={Boolean(selectedSymbol)}
        onClose={() => setSelectedSymbol(null)}
      />
    </section>
  );
}

function DDirectionCard({
  symbol,
  data,
  isOff,
  digits,
  locale,
  onClick,
}: {
  symbol: string;
  data?: DDirectionSymbolData;
  isOff: boolean;
  digits: number;
  locale: "VN" | "EN";
  onClick: () => void;
}) {
  const dDir = data?.d_direction || "WAIT";
  const dState = data?.d_state || "MISSING";
  const candle = data?.candle;

  const isDoji = Boolean(
    data?.raw_direction === "DOJI" ||
    dState === "DOJI" ||
    (candle && candle.open !== null && String(candle.open) === String(candle.close))
  );

  const isUp = Boolean(candle && candle.close !== null && candle.open !== null && candle.close > candle.open);

  const color = isDoji
    ? "var(--terminal-warning)"
    : isUp || dDir === "BUY"
    ? "var(--terminal-accent)"
    : dDir === "SELL"
    ? "var(--terminal-danger)"
    : "var(--muted)";

  return (
    <button
      type="button"
      onClick={onClick}
      className="terminal-panel flex flex-col justify-between rounded-xl p-3.5 text-left transition-all hover:border-[var(--terminal-accent)]/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)]"
    >
      <div>
        <div className="flex items-center justify-between border-b border-[var(--panel-border)]/60 pb-2">
          <span className="font-mono text-sm font-black text-[var(--foreground)]">{symbol}</span>
          <div className="flex items-center gap-1.5">
            {isOff && (
              <span className="rounded bg-[var(--surface-raised)] px-1.5 py-0.5 font-mono text-[9px] font-bold text-[var(--muted)]">
                OFF
              </span>
            )}
            <span
              className="rounded px-2 py-0.5 font-mono text-[11px] font-black"
              style={{
                color,
                backgroundColor: `color-mix(in srgb, ${color} 15%, transparent)`,
              }}
            >
              {dDir}
            </span>
          </div>
        </div>

        <div className="mt-2 space-y-1 font-mono text-[11px]">
          <div className="flex justify-between text-[10px] text-[var(--muted)]">
            <span>Session:</span>
            <span className="font-bold text-[var(--foreground)]">{data?.session_date || "—"}</span>
          </div>

          <div className="flex justify-between text-[10px]">
            <span className="text-[var(--muted)]">M30 Broker:</span>
            <span className="font-mono font-bold text-[var(--foreground)]">
              {data?.d_candle_open_time_broker || "—"} → {data?.d_candle_close_time_broker || "—"}
            </span>
          </div>

          <div className="flex justify-between text-[10px]">
            <span className="text-[var(--muted)]">Local GMT+7:</span>
            <span className="font-mono font-bold text-[var(--terminal-accent)]">
              {data?.d_candle_open_time_local || "—"} → {data?.d_candle_close_time_local || "—"}
            </span>
          </div>
        </div>
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-[var(--panel-border)]/60 pt-2.5">
        <MiniCandleChart candle={candle} color={color} isDoji={isDoji} isUp={isUp} />
        <div className="text-right font-mono text-[10px] space-y-0.5">
          <div><span className="text-[var(--muted)]">O: </span><span className="font-bold">{formatPrice(candle?.open, digits)}</span></div>
          <div><span className="text-[var(--muted)]">C: </span><span className="font-bold text-[var(--foreground)]">{formatPrice(candle?.close, digits)}</span></div>
        </div>
      </div>
    </button>
  );
}

function MiniCandleChart({
  candle,
  color,
  isDoji,
  isUp,
}: {
  candle?: { open: number | null; high: number | null; low: number | null; close: number | null } | null;
  color: string;
  isDoji: boolean;
  isUp: boolean;
}) {
  if (!candle || candle.open === null || candle.close === null) {
    return <span className="font-mono text-[10px] text-[var(--muted)]">—</span>;
  }

  return (
    <svg width="28" height="32" viewBox="0 0 28 32" className="overflow-visible">
      <line x1="14" y1="2" x2="14" y2="30" stroke={color} strokeWidth="1.5" />
      <rect
        x="7"
        y={isDoji ? "14" : isUp ? "8" : "8"}
        width="14"
        height={isDoji ? "3" : "16"}
        fill={isDoji ? "none" : color}
        stroke={color}
        strokeWidth="1.5"
      />
    </svg>
  );
}

function formatPrice(val: number | null | undefined, digits: number): string {
  if (val === null || val === undefined) return "—";
  return Number(val).toFixed(digits);
}
