"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useLocale } from "./LocaleProvider";

const TCBS = "https://apipubaws.tcbs.com.vn/stock-insight";

interface StockLookupData {
  symbol: string;
  overview: {
    symbol: string;
    name: string;
    exchange: string;
    industry: string;
    market_cap: number;
    market_cap_display: string;
    pe: number;
    pb: number;
    roe: number;
    eps: number;
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
  }[];
  foreign: {
    foreign_ratio: number;
    foreign_buy_volume: number;
    foreign_sell_volume: number;
  };
}

function formatCap(value: number): string {
  if (!value) return "N/A";
  if (value >= 1e12) return `${(value / 1e12).toFixed(1)} nghìn tỷ`;
  if (value >= 1e9) return `${(value / 1e9).toFixed(0)} tỷ`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(0)} triệu`;
  return value.toLocaleString("vi-VN");
}

function formatPct(value: number): string {
  if (!value && value !== 0) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

async function fetchTCBS(symbol: string): Promise<StockLookupData> {
  const headers = { Accept: "application/json", "User-Agent": "Mozilla/5.0" };
  const opts: RequestInit = { headers, signal: AbortSignal.timeout(12000) };

  const [ovRaw, finRaw, divRaw, forRaw] = await Promise.allSettled([
    fetch(`${TCBS}/v1/stock/${symbol}/overview`, opts),
    fetch(`${TCBS}/v1/stock/${symbol}/financial-declaration`, opts),
    fetch(`${TCBS}/v2/stock/${symbol}/dividend-history`, opts),
    fetch(`${TCBS}/v1/stock/${symbol}/ownership`, opts),
  ]);

  const extract = (r: PromiseSettledResult<Response>): any => {
    if (r.status === "rejected") return null;
    if (!r.value.ok) return null;
    return r.value.json();
  };
  const extractData = (raw: any): any => {
    if (!raw) return null;
    const d = raw.data ?? raw;
    return Array.isArray(d) && d.length > 0 ? d[0] : d;
  };
  const extractList = (raw: any): any[] => {
    if (!raw) return [];
    const d = raw.data ?? raw;
    return Array.isArray(d) ? d : [];
  };

  const ov = extractData(await extract(ovRaw)) || {};
  const finList = extractList(await extract(finRaw));
  const divList = extractList(await extract(divRaw));
  const forData = extractData(await extract(forRaw)) || {};

  return {
    symbol: symbol.toUpperCase(),
    overview: {
      symbol: symbol.toUpperCase(),
      name: ov.companyName || ov.name || symbol.toUpperCase(),
      exchange: ov.exchange || "",
      industry: ov.industry || "",
      market_cap: ov.marketCap || 0,
      market_cap_display: formatCap(ov.marketCap || 0),
      pe: ov.pe || 0,
      pb: ov.pb || 0,
      roe: ov.roe || 0,
      eps: ov.eps || 0,
    },
    financials: finList.slice(0, 4).map((f: any) => ({
      period: f.period || "",
      quarter: f.quarter || "",
      year: f.year || "",
      revenue: f.revenue || 0,
      revenue_yoy: f.revenueYoy || 0,
      net_profit: f.netProfit || 0,
      net_profit_yoy: f.netProfitYoy || 0,
      eps: f.eps || 0,
      roe: f.roe || 0,
    })),
    dividends: divList.slice(0, 10).map((d: any) => ({
      ex_date: d.exDividendDate || d.exDate || "",
      cash_dividend: d.cashDividend || d.dividendPerShare || 0,
      stock_dividend: d.stockDividend || 0,
    })),
    foreign: {
      foreign_ratio: forData.foreignOwnershipRatio || forData.foreignPercent || 0,
      foreign_buy_volume: forData.foreignBuyVolume || 0,
      foreign_sell_volume: forData.foreignSellVolume || 0,
    },
  };
}

export function StockLookupModal({
  initialSymbol,
  isOpen,
  onClose,
}: {
  initialSymbol: string | null;
  isOpen: boolean;
  onClose: () => void;
}) {
  const { locale } = useLocale();
  const t = (vn: string, en: string) => (locale === "EN" ? en : vn);

  const [searchInput, setSearchInput] = useState("");
  const [activeSymbol, setActiveSymbol] = useState<string | null>(null);
  const [data, setData] = useState<StockLookupData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // When modal opens with initial symbol, auto-load it
  useEffect(() => {
    if (isOpen && initialSymbol) {
      setSearchInput(initialSymbol.toUpperCase());
      setActiveSymbol(initialSymbol.toUpperCase());
    } else if (isOpen) {
      setSearchInput("");
      setActiveSymbol(null);
      setData(null);
      setError(null);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen, initialSymbol]);

  // Fetch data when activeSymbol changes
  useEffect(() => {
    if (!activeSymbol) return;
    setLoading(true);
    setError(null);
    setData(null);
    fetchTCBS(activeSymbol)
      .then(setData)
      .catch((err) => setError(err.message || "Failed to fetch"))
      .finally(() => setLoading(false));
  }, [activeSymbol]);

  const doSearch = useCallback(() => {
    const sym = searchInput.trim().toUpperCase();
    if (sym.length >= 1 && sym.length <= 10) {
      setActiveSymbol(sym);
    }
  }, [searchInput]);

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

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      <div className="relative z-10 w-full max-w-2xl max-h-[85vh] overflow-y-auto rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)]">
        {/* Header with search */}
        <div className="sticky top-0 z-10 border-b border-[var(--panel-border)] bg-[var(--surface)] px-5 py-4">
          <div className="flex items-center justify-between gap-3 mb-3">
            <h2 className="font-mono text-sm font-black uppercase tracking-[0.15em] text-[var(--muted)]">
              {t("Tra cứu cổ phiếu", "Stock Lookup")}
            </h2>
            <button
              onClick={onClose}
              className="grid h-7 w-7 place-items-center rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
              aria-label="Close"
            >
              <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
                <path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === "Enter" && doSearch()}
              placeholder={t("Nhập mã cổ phiếu (VD: HPG, FPT, VCB)...", "Enter ticker (e.g. HPG, FPT, VCB)...")}
              className="flex-1 rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2 font-mono text-sm font-bold text-[var(--foreground)] placeholder:text-[var(--muted)]/50 focus:border-[var(--terminal-accent)]/50 focus:outline-none focus:ring-1 focus:ring-[var(--terminal-accent)]/30"
              maxLength={10}
            />
            <button
              onClick={doSearch}
              className="rounded-lg bg-[var(--terminal-accent)] px-4 py-2 font-mono text-xs font-black uppercase text-[#04130F] transition-colors hover:bg-[var(--terminal-accent-strong)]"
            >
              {t("Tra cứu", "Lookup")}
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="px-5 py-4">
          {!activeSymbol && !loading && (
            <div className="py-12 text-center">
              <div className="mx-auto mb-3 grid h-12 w-12 place-items-center rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--muted)]">
                <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5}>
                  <path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <p className="text-sm text-[var(--muted)]">
                {t("Nhập mã cổ phiếu và nhấn Enter để tra cứu", "Enter a ticker and press Enter to look up")}
              </p>
            </div>
          )}
          {loading && <LoadingSkeleton />}
          {error && (
            <div className="rounded-xl border border-[var(--terminal-danger)]/30 bg-[var(--terminal-danger)]/10 px-4 py-6 text-center">
              <p className="text-sm font-semibold text-[var(--terminal-danger)]">
                {activeSymbol}: {error}
              </p>
              <p className="mt-1 text-xs text-[var(--muted)]">
                {t("Kiểm tra lại mã hoặc thử mã khác", "Check the ticker or try another one")}
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
      {/* Company header */}
      <div className="flex items-center gap-3">
        <span className="font-mono text-xl font-black text-[var(--foreground)]">{ov.symbol}</span>
        <span className="text-sm font-semibold text-[var(--muted)]">{ov.name}</span>
        {ov.exchange && (
          <span className="rounded-md border border-[var(--panel-border)] bg-[var(--surface-raised)] px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-[var(--muted)]">
            {ov.exchange}
          </span>
        )}
      </div>

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
                        {t("DT", "Rev")}: {formatCap(f.revenue)}
                      </span>
                    )}
                  </div>
                  <div className="text-right">
                    <span className="font-mono text-sm font-black text-[var(--foreground)]">
                      {formatCap(f.net_profit)}
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
