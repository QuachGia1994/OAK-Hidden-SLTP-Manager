"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useLocale } from "./LocaleProvider";
import { getCompanyName, getMarketCap, getExchange } from "@/lib/stock-names";

type TabKey = "overview" | "reports" | "dividends" | "foreign" | "chart";

interface ProfileData {
  symbol: string;
  name: string;
  exchange: string;
  industry: string;
  market_cap: number;
  source: string;
  fetchedAt: string;
  stale: boolean;
}

interface ReportItem {
  period: string;
  type: string;
  publishedAt: string;
  pdfUrl: string;
  source: string;
  sourceUrl: string;
}

interface ReportsData {
  reports: ReportItem[];
  source: string;
  sourceUrl: string;
  fetchedAt: string;
  stale: boolean;
}

interface DividendItem {
  ex_date: string;
  pay_date: string;
  cash_amount: number;
  stock_ratio: number;
  source: string;
  sourceUrl: string;
}

interface DividendsData {
  dividends: DividendItem[];
  source: string;
  sourceUrl: string;
  fetchedAt: string;
  stale: boolean;
}

interface ForeignInfo {
  foreignRatio: number;
  recentTrades: { date: string; buyVol: number; sellVol: number }[];
  source: string;
  fetchedAt: string;
  stale: boolean;
}

async function fetchStockData<T>(symbol: string, file: string): Promise<T | null> {
  try {
    const res = await fetch(`/api/stock-data?symbol=${symbol}&file=${file}`);
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
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
  const t = useCallback((vn: string, en: string) => (locale === "EN" ? en : vn), [locale]);

  const [searchInput, setSearchInput] = useState("");
  const [activeSymbol, setActiveSymbol] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [profile, setProfile] = useState<ProfileData | null>(null);
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [reportsMeta, setReportsMeta] = useState<{ source: string; fetchedAt: string; stale: boolean } | null>(null);
  const [dividends, setDividends] = useState<DividendItem[]>([]);
  const [dividendsMeta, setDividendsMeta] = useState<{ source: string; fetchedAt: string; stale: boolean } | null>(null);
  const [foreign, setForeign] = useState<ForeignInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isOpen && initialSymbol) {
      setSearchInput(initialSymbol.toUpperCase());
      setActiveSymbol(initialSymbol.toUpperCase());
      setActiveTab("overview");
    } else if (isOpen) {
      setSearchInput("");
      setActiveSymbol(null);
      setProfile(null);
      setReports([]);
      setReportsMeta(null);
      setDividends([]);
      setDividendsMeta(null);
      setForeign(null);
      setError(null);
      setActiveTab("overview");
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen, initialSymbol]);

  useEffect(() => {
    if (!activeSymbol) return;
    setLoading(true);
    setError(null);
    setProfile(null);
    setReports([]);
    setReportsMeta(null);
    setDividends([]);
    setDividendsMeta(null);
    setForeign(null);

    Promise.allSettled([
      fetchStockData<ProfileData>(activeSymbol, "profile"),
      fetchStockData<ReportsData>(activeSymbol, "reports"),
      fetchStockData<DividendsData>(activeSymbol, "dividends"),
      fetchStockData<ForeignInfo>(activeSymbol, "foreign-trading"),
    ]).then(([prof, rep, div, forr]) => {
      const p = prof.status === "fulfilled" ? prof.value : null;
      const r = rep.status === "fulfilled" ? rep.value : null;
      const d = div.status === "fulfilled" ? div.value : null;
      const f = forr.status === "fulfilled" ? forr.value : null;

      if (!p && !r && !d && !f) {
        setError(t("Không tìm thấy dữ liệu", "No data found"));
      } else {
        if (p) setProfile(p);
        if (r?.reports) {
          setReports(r.reports);
          setReportsMeta({ source: r.source, fetchedAt: r.fetchedAt, stale: r.stale });
        }
        if (d?.dividends) {
          setDividends(d.dividends);
          setDividendsMeta({ source: d.source, fetchedAt: d.fetchedAt, stale: d.stale });
        }
        if (f) setForeign(f);
      }
    }).catch(() => setError("Failed to load"))
      .finally(() => setLoading(false));
  }, [activeSymbol, t]);

  const doSearch = useCallback(() => {
    const sym = searchInput.trim().toUpperCase();
    if (sym.length >= 1 && sym.length <= 10) {
      setActiveSymbol(sym);
      setActiveTab("overview");
    }
  }, [searchInput]);

  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === "Escape") onClose();
  }, [onClose]);

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

  const sym = activeSymbol || "";
  const companyName = profile?.name || (sym ? getCompanyName(sym) : "");
  const exchange = profile?.exchange || (sym ? getExchange(sym) : "");

  const tabs: { key: TabKey; label: string }[] = [
    { key: "overview", label: t("Tổng quan", "Overview") },
    { key: "reports", label: "BCTC" },
    { key: "dividends", label: t("Cổ tức", "Dividends") },
    { key: "foreign", label: t("Khối ngoại", "Foreign") },
    { key: "chart", label: t("Biểu đồ", "Chart") },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />

      <div className="relative z-10 w-full max-w-lg max-h-[85vh] overflow-y-auto rounded-2xl border border-[var(--panel-border)] bg-[var(--surface)]">
        {/* Header + Search */}
        <div className="sticky top-0 z-10 border-b border-[var(--panel-border)] bg-[var(--surface)] px-5 py-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="font-mono text-sm font-black uppercase tracking-[0.15em] text-[var(--muted)]">
              {t("Tra cứu cổ phiếu", "Stock Lookup")}
            </h2>
            <button onClick={onClose} className="grid h-7 w-7 place-items-center rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--muted)] hover:text-[var(--foreground)]" aria-label="Close">
              <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M18 6 6 18M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" /></svg>
            </button>
          </div>
          <div className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value.toUpperCase())}
              onKeyDown={(e) => e.key === "Enter" && doSearch()}
              placeholder={t("Nhập mã (VD: HPG)...", "Ticker (e.g. HPG)...")}
              className="flex-1 rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2 font-mono text-sm font-bold text-[var(--foreground)] placeholder:text-[var(--muted)]/50 focus:border-[var(--terminal-accent)]/50 focus:outline-none"
              maxLength={10}
            />
            <button onClick={doSearch} className="rounded-lg bg-[var(--terminal-accent)] px-4 py-2 font-mono text-xs font-black uppercase text-[#04130F] hover:bg-[var(--terminal-accent-strong)]">
              {t("Tra cứu", "Go")}
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="px-5 py-4">
          {!activeSymbol && (
            <div className="py-10 text-center text-sm text-[var(--muted)]">
              {t("Nhập mã và nhấn Enter", "Enter a ticker and press Enter")}
            </div>
          )}

          {activeSymbol && !loading && error && (
            <div className="rounded-xl border border-[var(--terminal-danger)]/30 bg-[var(--terminal-danger)]/10 px-4 py-6 text-center">
              <p className="text-sm font-semibold text-[var(--terminal-danger)]">{activeSymbol}: {error}</p>
            </div>
          )}

          {activeSymbol && loading && (
            <div className="space-y-3 animate-pulse">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 rounded-xl bg-[var(--surface-raised)]" />
              ))}
            </div>
          )}

          {activeSymbol && !loading && !error && (
            <>
              {/* Stock header */}
              <div className="mb-3 flex items-center gap-3">
                <span className="font-mono text-xl font-black text-[var(--foreground)]">{sym}</span>
                {exchange && <span className="rounded-md border border-[var(--panel-border)] bg-[var(--surface-raised)] px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-[var(--muted)]">{exchange}</span>}
                {companyName && <span className="text-sm text-[var(--muted)] truncate">{companyName}</span>}
              </div>

              {/* Tabs */}
              <div className="mb-4 flex gap-1 overflow-x-auto border-b border-[var(--panel-border)]">
                {tabs.map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`whitespace-nowrap px-3 py-2 text-[11px] font-bold uppercase tracking-wide transition-colors ${
                      activeTab === tab.key
                        ? "border-b-2 border-[var(--terminal-accent)] text-[var(--terminal-accent)]"
                        : "text-[var(--muted)] hover:text-[var(--foreground)]"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>

              {/* Tab content */}
              {activeTab === "overview" && <OverviewTab profile={profile} t={t} />}
              {activeTab === "reports" && <ReportsTab reports={reports} meta={reportsMeta} t={t} />}
              {activeTab === "dividends" && <DividendsTab dividends={dividends} meta={dividendsMeta} t={t} />}
              {activeTab === "foreign" && <ForeignTab foreign={foreign} t={t} />}
              {activeTab === "chart" && <ChartTab symbol={sym} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function OverviewTab({ profile, t }: { profile: ProfileData | null; t: (vn: string, en: string) => string }) {
  if (!profile) return <EmptyState text={t("Chưa có dữ liệu tổng quan", "No overview data")} />;
  return (
    <div className="space-y-3">
      <Row label={t("Nguồn", "Source")} value={profile.source} />
      <Row label={t("Ngành", "Industry")} value={profile.industry || "—"} />
      <Row label={t("Vốn hoá", "Market Cap")} value={profile.market_cap ? `${(profile.market_cap / 1e9).toFixed(0)} tỷ` : "—"} />
      {profile.fetchedAt && (
        <p className="text-[10px] text-[var(--muted)]">
          {t("Cập nhật", "Updated")}: {new Date(profile.fetchedAt).toLocaleDateString("vi-VN")}
          {profile.stale && <span className="ml-1 text-[var(--terminal-warning)]">({t("cũ", "stale")})</span>}
        </p>
      )}
    </div>
  );
}

type MetaInfo = { source: string; fetchedAt: string; stale: boolean } | null;

function ReportsTab({ reports, meta, t }: { reports: ReportItem[]; meta: MetaInfo; t: (vn: string, en: string) => string }) {
  if (!reports.length) return <EmptyState text={t("Chưa có báo cáo tài chính", "No financial reports")} />;
  return (
    <div className="space-y-2">
      {reports.map((r, i) => (
        <div key={i} className="flex items-center justify-between rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2.5">
          <div>
            <span className="font-mono text-xs font-bold text-[var(--foreground)]">{r.period}</span>
            <span className="ml-2 text-[10px] text-[var(--muted)]">{r.type}</span>
          </div>
          <div className="flex items-center gap-1.5">
            {r.pdfUrl && (
              <>
                <a
                  href={r.pdfUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-md bg-[var(--terminal-accent)]/10 px-2.5 py-1 font-mono text-[10px] font-bold text-[var(--terminal-accent)] hover:bg-[var(--terminal-accent)]/20"
                >
                  PDF
                </a>
                <a
                  href={r.pdfUrl}
                  download
                  className="rounded-md border border-[var(--panel-border)] px-2 py-1 font-mono text-[10px] font-bold text-[var(--muted)] hover:text-[var(--foreground)]"
                  title={t("Tải xuống", "Download")}
                >
                  <svg className="h-3 w-3 inline" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" strokeLinecap="round" strokeLinejoin="round" /></svg>
                </a>
              </>
            )}
          </div>
        </div>
      ))}
      {meta && (
        <p className="text-[10px] text-[var(--muted)] pt-1">
          {t("Nguồn", "Source")}: {meta.source} | {t("Cập nhật", "Updated")}: {new Date(meta.fetchedAt).toLocaleDateString("vi-VN")}
          {meta.stale && <span className="ml-1 text-[var(--terminal-warning)]">({t("cũ", "stale")})</span>}
        </p>
      )}
    </div>
  );
}

function DividendsTab({ dividends, meta, t }: { dividends: DividendItem[]; meta: MetaInfo; t: (vn: string, en: string) => string }) {
  if (!dividends.length) return <EmptyState text={t("Chưa có dữ liệu cổ tức", "No dividend data")} />;
  return (
    <div className="space-y-2">
      {dividends.map((d, i) => (
        <div key={i} className="flex items-center justify-between rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2">
          <span className="font-mono text-xs text-[var(--muted)]">{d.ex_date}</span>
          <div className="flex items-center gap-2">
            {d.cash_amount > 0 && (
              <span className="rounded-md bg-[var(--terminal-accent)]/10 px-2 py-0.5 font-mono text-[10px] font-bold text-[var(--terminal-accent)]">
                {d.cash_amount.toLocaleString("vi-VN")}đ
              </span>
            )}
            {d.stock_ratio > 0 && (
              <span className="rounded-md bg-[var(--terminal-warning)]/10 px-2 py-0.5 font-mono text-[10px] font-bold text-[var(--terminal-warning)]">
                {d.stock_ratio}%
              </span>
            )}
          </div>
        </div>
      ))}
      {meta && (
        <p className="text-[10px] text-[var(--muted)] pt-1">
          {t("Nguồn", "Source")}: {meta.source} | {t("Cập nhật", "Updated")}: {new Date(meta.fetchedAt).toLocaleDateString("vi-VN")}
          {meta.stale && <span className="ml-1 text-[var(--terminal-warning)]">({t("cũ", "stale")})</span>}
        </p>
      )}
    </div>
  );
}

function ForeignTab({ foreign, t }: { foreign: ForeignInfo | null; t: (vn: string, en: string) => string }) {
  if (!foreign) return <EmptyState text={t("Chưa có dữ liệu khối ngoại", "No foreign trading data")} />;
  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-3">
        <span className="font-mono text-2xl font-black text-[var(--foreground)]">
          {foreign.foreignRatio ? `${foreign.foreignRatio.toFixed(1)}%` : "—"}
        </span>
        <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-[var(--surface)]">
          <div className="h-full rounded-full bg-[var(--terminal-accent)]" style={{ width: `${Math.min(foreign.foreignRatio || 0, 100)}%` }} />
        </div>
      </div>
      {foreign.recentTrades.length > 0 && (
        <div className="space-y-1.5">
          {foreign.recentTrades.slice(0, 5).map((t2, i) => (
            <div key={i} className="flex items-center justify-between rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2 text-xs">
              <span className="font-mono text-[var(--muted)]">{t2.date}</span>
              <span className="text-[var(--terminal-accent)]">Mua: {t2.buyVol.toLocaleString()}</span>
              <span className="text-[var(--terminal-danger)]">Bán: {t2.sellVol.toLocaleString()}</span>
            </div>
          ))}
        </div>
      )}
      {foreign.fetchedAt && (
        <p className="text-[10px] text-[var(--muted)]">
          {t("Nguồn", "Source")}: {foreign.source} | {t("Cập nhật", "Updated")}: {new Date(foreign.fetchedAt).toLocaleDateString("vi-VN")}
        </p>
      )}
    </div>
  );
}

function ChartTab({ symbol }: { symbol: string }) {
  return (
    <div className="py-8 text-center">
      <a
        href={`https://www.tradingview.com/symbols/HOSE-${symbol}/`}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 rounded-xl bg-[var(--terminal-accent)] px-5 py-3 font-mono text-sm font-black uppercase text-[#04130F] hover:bg-[var(--terminal-accent-strong)]"
      >
        Mở biểu đồ trên TradingView
        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </a>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2">
      <span className="text-xs text-[var(--muted)]">{label}</span>
      <span className="font-mono text-sm font-bold text-[var(--foreground)]">{value}</span>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="py-8 text-center text-sm text-[var(--muted)]">
      {text}
    </div>
  );
}
