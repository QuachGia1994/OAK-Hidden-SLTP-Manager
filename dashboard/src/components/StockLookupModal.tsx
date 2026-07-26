"use client";

import { useState, useEffect, useCallback } from "react";
import { useLocale } from "./LocaleProvider";

interface StockLookupData {
  symbol: string;
  overview: {
    symbol: string;
    name: string;
    exchange: string;
    industry: string;
    market_cap: number;
    market_cap_display: string;
    ceo: string;
    website: string;
    pe: number;
    pb: number;
    roe: number;
    eps: number;
    outstanding_shares: number;
  };
  financials: {
    period: string;
    quarter: string;
    year: string;
    revenue: number;
    revenue_yoy: number;
    net_profit: number;
    net_profit_yoy: number;
    eps: number;
    roe: number;
  }[];
  dividends: {
    ex_date: string;
    cash_dividend: number;
    stock_dividend: number;
    ratio: string;
  }[];
  foreign: {
    foreign_ratio: number;
    foreign_buy_volume: number;
    foreign_sell_volume: number;
  };
}

function formatBil(value: number): string {
  if (!value) return "—";
  if (Math.abs(value) >= 1e12) return `${(value / 1e12).toFixed(1)} nghìn tỷ`;
  if (Math.abs(value) >= 1e9) return `${(value / 1e9).toFixed(1)} tỷ`;
  if (Math.abs(value) >= 1e6) return `${(value / 1e6).toFixed(0)} triệu`;
  return value.toLocaleString("vi-VN");
}

function formatPct(value: number): string {
  if (!value && value !== 0) return "—";
  const sign = value >= 0 ? "+" : "";
  return `${sign}${value.toFixed(1)}%`;
}

export function StockLookupModal({
  symbol,
  isOpen,
  onClose,
}: {
  symbol: string | null;
  isOpen: boolean;
  onClose: () => void;
}) {
  const { locale } = useLocale();
  const [data, setData] = useState<StockLookupData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isOpen || !symbol) {
      setData(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    fetch(`/api/stock-lookup?symbol=${encodeURIComponent(symbol)}`)
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json) => {
        if (json.error) throw new Error(json.error);
        setData(json);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [symbol, isOpen]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    },
    [onClose],
  );

  useEffect(() => {
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [isOpen, handleKeyDown]);

  if (!isOpen || !symbol) return null;

  const t = (vn: string, en: string) => (locale === "EN" ? en : vn);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      {/* Modal */}
      <div className="relative z-10 w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)] shadow-2xl">
        {/* Header */}
        <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[var(--panel-border)] bg-[var(--surface)] px-5 py-4">
          <div>
            <h2 className="font-mono text-lg font-black text-[var(--foreground)]">
              {symbol}
              <span className="ml-2 text-sm font-semibold text-[var(--muted)]">
                {data?.overview?.name || ""}
              </span>
            </h2>
            {data?.overview?.exchange && (
              <span className="mt-1 inline-block rounded-md border border-[var(--panel-border)] bg-[var(--surface-raised)] px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-[var(--muted)]">
                {data.overview.exchange}
              </span>
            )}
          </div>
          <button
            onClick={onClose}
            className="grid h-8 w-8 place-items-center rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--muted)] transition-colors hover:bg-[var(--surface)] hover:text-[var(--foreground)]"
            aria-label="Close"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="px-5 py-4">
          {loading && <LoadingSkeleton />}
          {error && (
            <div className="rounded-xl border border-[var(--terminal-danger)]/30 bg-[var(--terminal-danger)]/10 px-4 py-6 text-center">
              <p className="text-sm font-semibold text-[var(--terminal-danger)]">
                {t("Không thể tải dữ liệu", "Failed to load data")}: {error}
              </p>
            </div>
          )}
          {data && !loading && <LookupContent data={data} locale={locale} />}
        </div>
      </div>
    </div>
  );
}

function LookupContent({ data, locale }: { data: StockLookupData; locale: "VN" | "EN" }) {
  const t = (vn: string, en: string) => (locale === "EN" ? en : vn);
  const ov = data.overview;

  return (
    <div className="space-y-4">
      {/* Overview metrics */}
      <Section title={t("TỔNG QUAN", "OVERVIEW")}>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MetricBox label={t("Vốn hoá", "Market Cap")} value={ov.market_cap_display} />
          <MetricBox label="PE" value={ov.pe ? ov.pe.toFixed(1) : "—"} />
          <MetricBox label="EPS" value={ov.eps ? ov.eps.toLocaleString("vi-VN") : "—"} />
          <MetricBox label="ROE" value={ov.roe ? `${ov.roe.toFixed(1)}%` : "—"} />
        </div>
        {ov.industry && (
          <p className="mt-2 text-xs text-[var(--muted)]">
            {t("Ngành", "Industry")}: {ov.industry}
          </p>
        )}
      </Section>

      {/* LNST 4Q */}
      {data.financials.length > 0 && (
        <Section title={t("LNST 4 QUÝ GẦN NHẤT", "LAST 4 QUARTERS NET PROFIT")}>
          <div className="space-y-2">
            {data.financials.map((f, i) => {
              const yoy = f.net_profit_yoy;
              const trendUp = yoy >= 0;
              return (
                <div
                  key={i}
                  className="flex items-center justify-between rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2.5"
                >
                  <div>
                    <span className="font-mono text-xs font-bold text-[var(--foreground)]">
                      {f.quarter && f.year ? `Q${f.quarter}/${f.year}` : f.period || `Q${i + 1}`}
                    </span>
                    {f.revenue > 0 && (
                      <span className="ml-2 text-[10px] text-[var(--muted)]">
                        {t("DT", "Rev")}: {formatBil(f.revenue)}
                      </span>
                    )}
                  </div>
                  <div className="text-right">
                    <span className="font-mono text-sm font-black text-[var(--foreground)]">
                      {formatBil(f.net_profit)}
                    </span>
                    {yoy !== 0 && (
                      <span
                        className={`ml-2 font-mono text-xs font-bold ${
                          trendUp ? "text-[var(--terminal-accent)]" : "text-[var(--terminal-danger)]"
                        }`}
                      >
                        {trendUp ? "▲" : "▼"} {formatPct(yoy)}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </Section>
      )}

      {/* Dividends */}
      {data.dividends.length > 0 && (
        <Section title={t("LỊCH CHIA CỔ TỨC", "DIVIDEND HISTORY")}>
          <div className="space-y-1.5">
            {data.dividends.map((d, i) => (
              <div
                key={i}
                className="flex items-center justify-between rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2"
              >
                <span className="font-mono text-xs text-[var(--muted)]">{d.ex_date || "—"}</span>
                <div className="flex items-center gap-2">
                  {d.cash_dividend > 0 && (
                    <span className="rounded-md bg-[var(--terminal-accent)]/10 px-2 py-0.5 font-mono text-[10px] font-bold text-[var(--terminal-accent)]">
                      {d.cash_dividend.toLocaleString("vi-VN")}đ
                    </span>
                  )}
                  {d.stock_dividend > 0 && (
                    <span className="rounded-md bg-[var(--terminal-warning)]/10 px-2 py-0.5 font-mono text-[10px] font-bold text-[var(--terminal-warning)]">
                      {d.stock_dividend}%
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {/* Foreign ownership */}
      <Section title={t("TỶ LỆ NƯỚC NGOÀI NẮM GIỮ", "FOREIGN OWNERSHIP")}>
        <div className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-3">
          <div className="mb-2 flex items-end justify-between">
            <span className="font-mono text-2xl font-black text-[var(--foreground)]">
              {data.foreign.foreign_ratio ? `${data.foreign.foreign_ratio.toFixed(1)}%` : "—"}
            </span>
            <div className="flex gap-3 text-[10px] font-semibold text-[var(--muted)]">
              {data.foreign.foreign_buy_volume > 0 && (
                <span>
                  {t("Mua", "Buy")}: {data.foreign.foreign_buy_volume.toLocaleString("vi-VN")}
                </span>
              )}
              {data.foreign.foreign_sell_volume > 0 && (
                <span>
                  {t("Bán", "Sell")}: {data.foreign.foreign_sell_volume.toLocaleString("vi-VN")}
                </span>
              )}
            </div>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-[var(--surface)]">
            <div
              className="h-full rounded-full bg-[var(--terminal-accent)] transition-all duration-500"
              style={{ width: `${Math.min(data.foreign.foreign_ratio || 0, 100)}%` }}
            />
          </div>
        </div>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface)] p-4">
      <h3 className="mb-3 font-mono text-[10px] font-black uppercase tracking-[0.2em] text-[var(--muted)]">
        {title}
      </h3>
      {children}
    </div>
  );
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2.5">
      <div className="text-[10px] font-bold uppercase tracking-wider text-[var(--muted)]">{label}</div>
      <div className="mt-0.5 font-mono text-base font-black text-[var(--foreground)]">{value}</div>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-4 animate-pulse">
      {[1, 2, 3].map((i) => (
        <div key={i} className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] p-4">
          <div className="mb-3 h-3 w-24 rounded bg-[var(--surface)]" />
          <div className="space-y-2">
            <div className="h-8 w-full rounded bg-[var(--surface)]" />
            <div className="h-8 w-3/4 rounded bg-[var(--surface)]" />
          </div>
        </div>
      ))}
    </div>
  );
}
