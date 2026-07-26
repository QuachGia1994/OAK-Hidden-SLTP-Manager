"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useLocale } from "./LocaleProvider";
import { getCompanyName, getMarketCap, getExchange, getIndustry } from "@/lib/stock-names";

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

interface TopShareholder {
  name: string;
  ratio: number;
  type: string;
}

interface ForeignInfo {
  foreignRatio: number;
  stateRatio: number;
  institutionalRatio: number;
  managementRatio: number;
  roomRemaining: number;
  topShareholders: TopShareholder[];
  source: string;
  sourceUrl: string;
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

    // Try static data first, fallback to realtime CafeF API
    Promise.allSettled([
      fetchStockData<ProfileData>(activeSymbol, "profile"),
      fetchStockData<ReportsData>(activeSymbol, "reports"),
      fetchStockData<DividendsData>(activeSymbol, "dividends"),
      fetchStockData<ForeignInfo>(activeSymbol, "foreign-trading"),
    ]).then(async ([prof, rep, div, forr]) => {
      const p = prof.status === "fulfilled" ? prof.value : null;
      const r = rep.status === "fulfilled" ? rep.value : null;
      const d = div.status === "fulfilled" ? div.value : null;
      const f = forr.status === "fulfilled" ? forr.value : null;

      // If static data exists, use it
      if (p || r?.reports || d?.dividends || f) {
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
        setLoading(false);
        return;
      }

      // No static data → try realtime CafeF API
      try {
        const rtRes = await fetch(`/api/stock-data-realtime?symbol=${activeSymbol}`);
        if (!rtRes.ok) {
          setError(t("Không tìm thấy dữ liệu", "No data found"));
          setLoading(false);
          return;
        }
        const rtData = await rtRes.json();

        if (rtData.profile) {
          const rp = rtData.profile as ProfileData;
          setProfile(rp);
        }
        if (rtData.dividends) {
          const rd = rtData.dividends as DividendsData;
          if (rd.dividends?.length) {
            setDividends(rd.dividends);
            setDividendsMeta({ source: rd.source, fetchedAt: rd.fetchedAt, stale: false });
          }
        }
        if (rtData.foreign) {
          const rf = rtData.foreign as ForeignInfo;
          setForeign(rf);
        }
        // Note: realtime doesn't return reports (static only)
      } catch {
        setError(t("Không tìm thấy dữ liệu", "No data found"));
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
  const companyName = (profile?.name && profile.name !== sym) ? profile.name : (sym ? getCompanyName(sym) : "");
  const exchange = profile?.exchange || (sym ? getExchange(sym) : "");

  const tabs: { key: TabKey; label: string }[] = [
    { key: "overview", label: t("Tổng quan", "Overview") },
    { key: "reports", label: t("Báo cáo", "Reports") },
    { key: "dividends", label: t("Cổ tức", "Dividends") },
    { key: "foreign", label: t("Cổ đông", "Shareholders") },
    { key: "chart", label: t("Biểu đồ", "Chart") },
  ];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="absolute inset-0 bg-[var(--primary)]/80 backdrop-blur-sm" onClick={onClose} />

      <div className="relative z-10 w-full max-w-2xl max-h-[90vh] min-h-[500px] overflow-y-auto rounded-[24px] border border-[var(--panel-border)] bg-[var(--surface)] p-6">
        {/* Header + Search */}
        <div className="sticky top-0 z-10 -mx-6 -mt-6 mb-6 border-b border-[var(--panel-border)] bg-[var(--surface)] px-6 py-5">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--muted)]">
              {t("Tra cứu cổ phiếu", "Stock Lookup")}
            </h2>
            <button onClick={onClose}
              className="grid h-7 w-7 place-items-center rounded-[14px] border border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--muted)] hover:text-[var(--foreground)] focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)]/40 focus-visible:outline-none"
              aria-label="Close">
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
              className="flex-1 rounded-[14px] border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2 font-mono text-sm font-bold text-[var(--foreground)] placeholder:text-[var(--muted)]/50 focus:border-[var(--terminal-accent)]/50 focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)]/20 focus-visible:outline-none"
              maxLength={10}
            />
            <button onClick={doSearch}
              className="rounded-[14px] bg-[var(--terminal-accent)] px-4 py-2 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--ink)] hover:bg-[var(--terminal-accent-strong)] focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)]/40 focus-visible:outline-none">
              {t("Tra cứu", "Go")}
            </button>
          </div>
        </div>

        {/* Content */}
        <div>
          {!activeSymbol && (
            <div className="py-10 text-center text-sm text-[var(--muted)]">
              {t("Nhập mã và nhấn Enter", "Enter a ticker and press Enter")}
            </div>
          )}

          {activeSymbol && !loading && error && (
            <div className="rounded-[14px] border border-[var(--terminal-danger)]/30 bg-[var(--terminal-danger)]/10 px-4 py-6 text-center">
              <p className="text-sm font-semibold text-[var(--terminal-danger)]">{activeSymbol}: {error}</p>
            </div>
          )}

          {activeSymbol && loading && (
            <div className="space-y-3 animate-pulse">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-16 rounded-[14px] bg-[var(--surface-raised)]" />
              ))}
            </div>
          )}

          {activeSymbol && !loading && !error && (
            <>
              {/* Stock header */}
              <div className="mb-3 flex items-center gap-3 pt-3">
                <span className="font-mono text-xl font-black text-[var(--foreground)]">{sym}</span>
                {exchange && <span className="rounded-[8px] border border-[var(--panel-border)] bg-[var(--surface-raised)] px-2 py-0.5 font-mono text-[10px] font-bold uppercase text-[var(--muted)]">{exchange}</span>}
                {companyName && <span className="text-sm text-[var(--muted)] truncate">{companyName}</span>}
              </div>

              {/* Tabs */}
              <div className="mb-4 flex gap-1 overflow-x-auto border-b border-[var(--panel-border)]">
                {tabs.map((tab) => (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTab(tab.key)}
                    className={`whitespace-nowrap px-3 py-2 text-[11px] font-bold uppercase tracking-[0.18em] transition-colors focus-visible:outline-none ${
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
              {activeTab === "overview" && <OverviewTab profile={profile} foreign={foreign} t={t} />}
              {activeTab === "reports" && <ReportsTab reports={reports} meta={reportsMeta} t={t} />}
              {activeTab === "dividends" && <DividendsTab dividends={dividends} meta={dividendsMeta} t={t} />}
              {activeTab === "foreign" && <ForeignTab foreign={foreign} t={t} />}
              {activeTab === "chart" && <ChartTab symbol={sym} t={t} />}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function OverviewTab({ profile, foreign, t }: { profile: ProfileData | null; foreign: ForeignInfo | null; t: (vn: string, en: string) => string }) {
  if (!profile) return <EmptyState text={t("Chưa có dữ liệu tổng quan", "No overview data")} />;

  // Market cap stored in "tỷ" units — display directly
  const formatCap = profile.market_cap > 0
    ? `${profile.market_cap.toLocaleString("vi-VN", { maximumFractionDigits: 2 })} tỷ`
    : "—";

  // Info columns matching FireAnt Hồ sơ
  const industry = profile.industry || (profile.symbol ? getIndustry(profile.symbol) : "");
  const leftInfo: { label: string; value: string }[] = [
    { label: t("Sàn", "Exchange"), value: profile.exchange || "—" },
    { label: t("Ngành", "Industry"), value: industry || "—" },
    { label: t("Vốn hoá", "Market Cap"), value: formatCap },
    { label: t("Nguồn", "Source"), value: profile.source },
  ];

  const rightInfo: { label: string; value: string }[] = [
    { label: t("Nước ngoài", "Foreign"), value: foreign ? `${foreign.foreignRatio.toFixed(1)}%` : "—" },
    { label: t("Tổ chức", "Institutional"), value: foreign ? `${foreign.institutionalRatio.toFixed(1)}%` : "—" },
    { label: t("Room NN", "Foreign Room"), value: foreign ? `${foreign.roomRemaining.toFixed(2)}%` : "—" },
  ];

  return (
    <div className="space-y-4">
      {/* Two-column info layout matching FireAnt */}
      <div className="grid grid-cols-2 gap-3">
        {/* Thông tin cơ bản */}
        <div className="rounded-[14px] border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-4">
          <h3 className="mb-3 text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--muted)]">
            {t("Thông tin cơ bản", "Basic Info")}
          </h3>
          <div className="space-y-2.5">
            {leftInfo.map((row, i) => (
              <div key={i} className="flex items-center justify-between">
                <span className="text-[11px] text-[var(--muted)]">{row.label}</span>
                <span className="font-mono text-xs font-bold text-[var(--foreground)]">{row.value}</span>
              </div>
            ))}
          </div>
        </div>
        {/* Thông tin cổ đông */}
        <div className="rounded-[14px] border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-4">
          <h3 className="mb-3 text-[10px] font-bold uppercase tracking-[0.18em] text-[var(--muted)]">
            {t("Cổ đông chính", "Key Shareholders")}
          </h3>
          <div className="space-y-2.5">
            {rightInfo.map((row, i) => (
              <div key={i} className="flex items-center justify-between">
                <span className="text-[11px] text-[var(--muted)]">{row.label}</span>
                <span className="font-mono text-xs font-bold text-[var(--foreground)]">{row.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

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
  return (
    <div className="space-y-4">
      <div>
        <h3 className="mb-2 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--muted)]">
          {t("Báo cáo tài chính", "Financial Reports")}
        </h3>
        {reports.length === 0 ? (
          <EmptyState text={t("Chưa có báo cáo tài chính", "No financial reports")} />
        ) : (
          <div className="space-y-2">
            {reports.map((r, i) => (
              <div key={i} className="flex items-center justify-between rounded-[14px] border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2.5">
                <div>
                  <span className="font-mono text-xs font-bold text-[var(--foreground)]">{r.period}</span>
                  <span className="ml-2 text-[10px] text-[var(--muted)]">{r.type}</span>
                </div>
                <div className="flex items-center gap-1.5">
                  {r.pdfUrl && (
                    <>
                      <a href={r.pdfUrl} target="_blank" rel="noopener noreferrer"
                        className="rounded-[8px] bg-[var(--terminal-accent)]/10 px-2.5 py-1 font-mono text-[10px] font-bold text-[var(--terminal-accent)] hover:bg-[var(--terminal-accent)]/20 focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)]/40 focus-visible:outline-none">
                        PDF
                      </a>
                      <a href={r.pdfUrl} download target="_blank" rel="noopener noreferrer"
                        className="rounded-[8px] border border-[var(--panel-border)] px-2 py-1 font-mono text-[10px] font-bold text-[var(--muted)] hover:text-[var(--foreground)] focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)]/40 focus-visible:outline-none"
                        title={t("Tải xuống", "Download")}>
                        <svg className="h-3 w-3 inline" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" strokeLinecap="round" strokeLinejoin="round" /></svg>
                      </a>
                    </>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      {meta && (
        <p className="text-[10px] text-[var(--muted)]">
          {t("Nguồn", "Source")}: {meta.source} | {t("Cập nhật", "Updated")}: {new Date(meta.fetchedAt).toLocaleDateString("vi-VN")}
          {meta.stale && <span className="ml-1 text-[var(--terminal-warning)]">({t("cũ", "stale")})</span>}
        </p>
      )}
    </div>
  );
}

function DividendsTab({ dividends, meta, t }: { dividends: DividendItem[]; meta: MetaInfo; t: (vn: string, en: string) => string }) {
  if (!dividends.length) return <EmptyState text={t("Chưa có dữ liệu cổ tức", "No dividend data")} />;

  // Group by year
  const byYear = new Map<string, DividendItem[]>();
  for (const d of dividends) {
    const year = d.ex_date?.slice(0, 4) || "—";
    if (!byYear.has(year)) byYear.set(year, []);
    byYear.get(year)!.push(d);
  }

  return (
    <div className="space-y-4">
      <h3 className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--muted)]">
        {t("Diễn biến cổ tức", "Dividend History")}
      </h3>

      {Array.from(byYear.entries()).map(([year, items]) => (
        <div key={year}>
          <div className="mb-2 flex items-center gap-2">
            <span className="font-mono text-xs font-black text-[var(--terminal-accent)]">{year}</span>
            <div className="flex-1 border-t border-[var(--panel-border)]" />
          </div>
          <div className="space-y-1.5">
            {items.map((d, i) => (
              <div key={i} className="flex items-center justify-between rounded-[14px] border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2.5">
                <div className="flex flex-col gap-0.5">
                  <span className="font-mono text-xs font-bold text-[var(--foreground)]">{d.ex_date}</span>
                  {d.pay_date && <span className="text-[10px] text-[var(--muted)]">{t("Thanh toán", "Pay")}: {d.pay_date}</span>}
                </div>
                <div className="flex items-center gap-2">
                  {d.cash_amount > 0 && (
                    <span className="rounded-[8px] bg-[var(--terminal-accent)]/10 px-2.5 py-1 font-mono text-[11px] font-bold text-[var(--terminal-accent)]">
                      {(d.cash_amount * 100).toLocaleString("vi-VN")}đ
                      <span className="ml-1 text-[9px] font-normal opacity-70">{t("/cp", "/share")}</span>
                    </span>
                  )}
                  {d.stock_ratio > 0 && (
                    <span className="rounded-[8px] bg-[var(--terminal-warning)]/10 px-2.5 py-1 font-mono text-[11px] font-bold text-[var(--terminal-warning)]">
                      {d.stock_ratio.toFixed(2)}%
                      <span className="ml-1 text-[9px] font-normal opacity-70">{t("cp", "stock")}</span>
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}

      {meta && (
        <p className="text-[10px] text-[var(--muted)]">
          {t("Nguồn", "Source")}: {meta.source} | {t("Cập nhật", "Updated")}: {new Date(meta.fetchedAt).toLocaleDateString("vi-VN")}
          {meta.stale && <span className="ml-1 text-[var(--terminal-warning)]">({t("cũ", "stale")})</span>}
        </p>
      )}
    </div>
  );
}

function ForeignTab({ foreign, t }: { foreign: ForeignInfo | null; t: (vn: string, en: string) => string }) {
  if (!foreign) return <EmptyState text={t("Chưa có dữ liệu cổ đông", "No shareholder data")} />;

  // Donut chart: 3 segments matching FireAnt — Nước ngoài, Nhà nước, Khác
  const donutSegments = [
    { label: t("Nước ngoài", "Foreign"), pct: foreign.foreignRatio || 0, color: "#5b8def" },
    { label: t("Nhà nước", "State"), pct: foreign.stateRatio || 0, color: "#00c991" },
    { label: t("Khác", "Others"), pct: Math.max(0, 100 - (foreign.foreignRatio || 0) - (foreign.stateRatio || 0)), color: "#f4b740" },
  ];

  // Right panel list: Ban lãnh đạo, Tổ chức, Nước ngoài (matching FireAnt)
  const groupList = [
    { label: t("Ban lãnh đạo", "Management"), pct: foreign.managementRatio || 0 },
    { label: t("Tổ chức", "Institutional"), pct: foreign.institutionalRatio || 0 },
    { label: t("Nước ngoài", "Foreign"), pct: foreign.foreignRatio || 0 },
  ];

  const r = 55;
  const circ = 2 * Math.PI * r;
  const strokeW = 14;
  let offset = 0;

  // Type badge color mapping
  const typeColors: Record<string, string> = {
    "BLĐ": "var(--terminal-accent)",
    "TC": "var(--terminal-warning)",
    "TN": "#5b8def",
  };

  return (
    <div className="space-y-4">
      {/* Cơ cấu sở hữu — two-panel layout matching FireAnt */}
      <div className="rounded-[14px] border border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-5">
        <h3 className="mb-1 text-center text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--muted)]">
          {t("Cơ cấu sở hữu", "Ownership Structure")}
        </h3>
        <p className="mb-4 text-center text-[10px] text-[var(--muted)] opacity-70">
          {t("Phân bố theo nhóm cổ đông", "Distribution by shareholder group")}
        </p>
        <div className="flex flex-wrap items-center justify-center gap-6">
          {/* Donut chart */}
          <svg width={140} height={140} viewBox="0 0 140 140" className="shrink-0">
            <circle cx={70} cy={70} r={r} fill="none" stroke="var(--surface)" strokeWidth={strokeW} />
            {donutSegments.map((seg, i) => {
              const len = (seg.pct / 100) * circ;
              const dash = `${len} ${circ - len}`;
              const el = (
                <circle
                  key={i}
                  cx={70} cy={70} r={r} fill="none"
                  stroke={seg.color} strokeWidth={strokeW}
                  strokeDasharray={dash}
                  strokeDashoffset={-offset}
                  strokeLinecap="butt"
                  transform="rotate(-90 70 70)"
                />
              );
              offset += len;
              return el;
            })}
            {/* Center text */}
            <text x={70} y={70} textAnchor="middle" dominantBaseline="central"
              className="fill-[var(--foreground)] font-mono text-[11px] font-bold">
              {foreign.foreignRatio.toFixed(1)}%
            </text>
          </svg>

          {/* Legend + group list */}
          <div className="space-y-3">
            {/* Donut legend */}
            <div className="space-y-1.5">
              {donutSegments.map((seg, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="h-3 w-3 rounded shrink-0" style={{ backgroundColor: seg.color }} />
                  <span className="text-[11px] text-[var(--muted)] min-w-[70px]">{seg.label}</span>
                  <span className="font-mono text-xs font-bold text-[var(--foreground)] tabular-nums">{seg.pct.toFixed(1)}%</span>
                </div>
              ))}
            </div>

            {/* Divider */}
            <div className="border-t border-[var(--panel-border)]" />

            {/* Nhóm cổ đông quan trọng */}
            <div>
              <p className="mb-1 text-[10px] font-bold uppercase tracking-[0.14em] text-[var(--muted)]">
                {t("Nhóm cổ đông quan trọng", "Key Shareholder Groups")}
              </p>
              <div className="space-y-1.5">
                {groupList.map((g, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <span className="text-[11px] text-[var(--muted)]">{g.label}</span>
                    <span className="font-mono text-xs font-bold text-[var(--foreground)] tabular-nums">{g.pct.toFixed(2)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Room NN info */}
        {foreign.roomRemaining > 0 && (
          <div className="mt-3 flex items-center justify-center gap-2">
            <span className="text-[10px] text-[var(--muted)]">{t("Room NN còn lại", "Foreign room left")}:</span>
            <span className="font-mono text-[11px] font-bold text-[var(--terminal-accent)]">{foreign.roomRemaining.toFixed(2)}%</span>
          </div>
        )}
      </div>

      {/* Top cổ đông lớn nhất */}
      {foreign.topShareholders && foreign.topShareholders.length > 0 && (
        <div className="rounded-[14px] border border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-4">
          <h3 className="mb-3 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--muted)]">
            {t("Top cổ đông lớn nhất", "Top Shareholders")}
          </h3>
          <div className="space-y-1.5">
            {foreign.topShareholders.slice(0, 10).map((sh, i) => (
              <div key={i} className="flex items-center justify-between py-1.5 border-b border-[var(--panel-border)] last:border-0">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="font-mono text-[10px] text-[var(--muted)] w-4 text-center">{i + 1}</span>
                  <span className="text-xs text-[var(--foreground)] truncate">{sh.name}</span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <span className="rounded-[6px] px-1.5 py-0.5 text-[9px] font-bold uppercase" style={{ backgroundColor: `color-mix(in srgb, ${typeColors[sh.type] || "var(--muted)"} 15%, transparent)`, color: typeColors[sh.type] || "var(--muted)" }}>{sh.type === "BLĐ" ? t("BLĐ", "Mgmt") : sh.type === "TC" ? t("TC", "Inst") : t("TN", "Fgn")}</span>
                  <span className="font-mono text-xs font-bold tabular-nums min-w-[45px] text-right" style={{ color: typeColors[sh.type] || "var(--foreground)" }}>{sh.ratio.toFixed(2)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {foreign.fetchedAt && (
        <p className="text-[10px] text-[var(--muted)]">
          {t("Nguồn", "Source")}: {foreign.source} | {t("Cập nhật", "Updated")}: {new Date(foreign.fetchedAt).toLocaleDateString("vi-VN")}
          {foreign.stale && <span className="ml-1 text-[var(--terminal-warning)]">({t("cũ", "stale")})</span>}
        </p>
      )}
    </div>
  );
}

function ChartTab({ symbol, t }: { symbol: string; t: (vn: string, en: string) => string }) {
  // Try multiple symbol formats — TradingView uses different exchange codes for VN
  const tvSymbols = [`HOSE:${symbol}`, `XVN:${symbol}`, symbol];
  const tvUrl = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSymbols[0])}`;

  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded-[14px] border border-[var(--panel-border)] bg-[var(--surface-raised)]">
        <iframe
          src={`https://s.tradingview.com/widgetembed/?frameElementId=tv_chart_${symbol}&symbol=${encodeURIComponent(tvSymbols[0])}&interval=D&theme=dark&style=1&locale=vi_VN&hide_side_toolbar=0&hide_top_toolbar=0&withdateranges=1&save_image=0&details=0&calendar=0&studies=[]&overrides=%7B%7D&enabled_features=%5B%5D&disabled_features=%5B%22header_symbol_search%22%2C%22show_domestic_time_over_non_domestic_popup%22%5D`}
          className="w-full"
          style={{ height: 400, border: "none" }}
          title={`${symbol} chart`}
          loading="lazy"
          sandbox="allow-scripts allow-same-origin allow-popups-to-escape-sandbox"
        />
      </div>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <p className="text-[10px] text-[var(--muted)]">
          {t("Một số mã VN có thể không có biểu đồ trên TradingView widget", "Some VN tickers may not have charts on TradingView widget")}
        </p>
        <a
          href={tvUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 rounded-[14px] bg-[var(--terminal-accent)]/10 px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--terminal-accent)] hover:bg-[var(--terminal-accent)]/20 focus-visible:ring-2 focus-visible:ring-[var(--terminal-accent)]/40 focus-visible:outline-none"
        >
          {t("Mở TradingView", "Open TradingView")}
          <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6M15 3h6v6M10 14L21 3" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </a>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-[14px] border border-[var(--panel-border)] bg-[var(--surface-raised)] px-3 py-2">
      <span className="text-[11px] font-bold uppercase tracking-[0.18em] text-[var(--muted)]">{label}</span>
      <span className="font-mono text-sm font-bold text-[var(--foreground)]">{value}</span>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="rounded-[14px] border border-[var(--panel-border)] bg-[var(--surface-raised)] px-4 py-8 text-center text-sm text-[var(--muted)]">
      {text}
    </div>
  );
}
