"use client";

import { useEffect, useRef } from "react";
import type { DDirectionSymbolData } from "@/lib/types";
import { useLocale } from "./LocaleProvider";

interface Props {
  symbolData: DDirectionSymbolData | null;
  open: boolean;
  onClose: () => void;
}

export function DDirectionDrawer({ symbolData, open, onClose }: Props) {
  const { locale } = useLocale();
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    drawerRef.current?.querySelector<HTMLElement>("button")?.focus();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open || !symbolData) return null;

  const digits = symbolData.price_digits || (symbolData.symbol === "GBPJPY" ? 3 : symbolData.symbol === "XAUUSD" ? 2 : 5);
  const candle = symbolData.candle;
  const isUp = candle && candle.close !== null && candle.open !== null && candle.close > candle.open;
  const isDoji =
    symbolData.raw_direction === "DOJI" ||
    symbolData.d_state === "DOJI" ||
    (candle && candle.open !== null && String(candle.open) === String(candle.close));

  const color = isDoji
    ? "var(--terminal-warning)"
    : isUp || symbolData.d_direction === "BUY"
    ? "var(--terminal-accent)"
    : "var(--terminal-danger)";

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true">
      <button
        type="button"
        className="fixed inset-0 cursor-default bg-black/65 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        ref={drawerRef}
        className="fixed inset-y-0 right-0 flex w-[min(560px,94vw)] flex-col overflow-hidden border-l border-[var(--panel-border)] bg-[var(--surface)] shadow-2xl max-md:inset-x-0 max-md:bottom-0 max-md:top-auto max-md:h-[85dvh] max-md:w-full max-md:rounded-t-2xl max-md:border-l-0 max-md:border-t"
      >
        <header className="flex items-center justify-between border-b border-[var(--panel-border)] bg-[var(--surface-raised)] px-5 py-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-base font-black text-[var(--foreground)]">
                {symbolData.symbol}
              </span>
              <span className="text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--terminal-accent)]">
                D-DIRECTION DETAIL
              </span>
            </div>
            <div className="mt-0.5 font-mono text-xs text-[var(--muted)]">
              Target: {symbolData.target_date} · Session: {symbolData.session_date || "—"}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex min-h-10 min-w-10 items-center justify-center rounded-lg text-[var(--muted)] transition-colors hover:bg-[var(--surface)] hover:text-[var(--foreground)]"
          >
            ×
          </button>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-5 space-y-5 font-mono text-xs">
          {/* SECTION: SUMMARY */}
          <section className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)]/60 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="terminal-kicker text-[var(--terminal-accent)]">D-DIRECTION RESULT</span>
              <span className="font-black text-sm" style={{ color }}>
                {symbolData.d_direction}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs pt-1">
              <div>
                <div className="text-[var(--muted)] text-[10px]">Execution Status</div>
                <div className="font-bold text-[var(--foreground)]">
                  {symbolData.execution_status === "OFF" ? "EXEC OFF (Tắt)" : "EXEC ON (Bật)"}
                </div>
              </div>
              <div>
                <div className="text-[var(--muted)] text-[10px]">D State</div>
                <div className="font-bold text-[var(--foreground)]">{symbolData.d_state}</div>
              </div>
              <div>
                <div className="text-[var(--muted)] text-[10px]">Broker M30 Window</div>
                <div className="font-bold text-[var(--foreground)]">
                  {symbolData.d_candle_open_time_broker || "—"} → {symbolData.d_candle_close_time_broker || "—"}
                </div>
              </div>
              <div>
                <div className="text-[var(--muted)] text-[10px]">Local GMT+7 Window</div>
                <div className="font-bold text-[var(--terminal-accent)]">
                  {symbolData.d_candle_open_time_local || "—"} → {symbolData.d_candle_close_time_local || "—"}
                </div>
              </div>
            </div>
          </section>

          {/* SECTION: CANDLE CHART & OHLC */}
          <section className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)]/60 p-4 space-y-3">
            <div className="flex items-center justify-between text-[11px] font-bold">
              <span>LAST COMPLETED M30 CANDLE</span>
              <span style={{ color }}>{symbolData.raw_direction || symbolData.d_direction}</span>
            </div>

            {candle && candle.open !== null && candle.close !== null ? (
              <div className="flex items-center justify-between gap-4 pt-2">
                <svg width="120" height="100" viewBox="0 0 120 100" className="mx-auto">
                  <line x1="60" y1="15" x2="60" y2="85" stroke={color} strokeWidth="2" />
                  <rect
                    x="42"
                    y={isDoji ? "48" : isUp ? "30" : "30"}
                    width="36"
                    height={isDoji ? "4" : "40"}
                    fill={isDoji ? "none" : color}
                    stroke={color}
                    strokeWidth="2"
                  />
                </svg>

                <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs font-mono">
                  <span className="text-[var(--muted)]">Open:</span>
                  <span className="text-right font-bold">{formatPrice(candle.open, digits)}</span>
                  <span className="text-[var(--muted)]">High:</span>
                  <span className="text-right font-bold">{formatPrice(candle.high, digits)}</span>
                  <span className="text-[var(--muted)]">Low:</span>
                  <span className="text-right font-bold">{formatPrice(candle.low, digits)}</span>
                  <span className="text-[var(--muted)]">Close:</span>
                  <span className="text-right font-bold text-[var(--foreground)]">
                    {formatPrice(candle.close, digits)}
                  </span>
                </div>
              </div>
            ) : (
              <div className="py-6 text-center text-[var(--muted)]">No candle data available</div>
            )}
          </section>

          {/* SECTION: RULE METADATA */}
          <section className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)]/60 p-4 space-y-1">
            <span className="terminal-kicker text-[var(--muted)]">DISCOVERY RULE</span>
            <div className="font-bold text-[var(--foreground)] pt-1 text-[11px]">
              {symbolData.discovery_rule}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function formatPrice(val: number | null, digits: number): string {
  if (val === null || val === undefined) return "—";
  return Number(val).toFixed(digits);
}
