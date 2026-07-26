"use client";

import { useState } from "react";
import { getCompanyName, getMarketCap, getExchange } from "@/lib/stock-names";
import type { StockAdvisorCandidate } from "@/lib/types";
import { StockLookupModal } from "@/components/StockLookupModal";

export function CandidateTableClient({
  candidates,
  locale,
  isVIP,
}: {
  candidates: StockAdvisorCandidate[];
  locale: "VN" | "EN";
  isVIP: boolean;
}) {
  const [filter100B, setFilter100B] = useState(true);
  const [lookupSymbol, setLookupSymbol] = useState<string | null>(null);
  const [lookupOpen, setLookupOpen] = useState(false);

  const displayCandidates = filter100B
    ? candidates.filter((c) => {
        const cap = getMarketCap(c.symbol, locale);
        return !cap.includes("nhỏ") && !cap.includes("<");
      })
    : candidates;

  const openLookup = (symbol: string) => {
    setLookupSymbol(symbol);
    setLookupOpen(true);
  };

  const openEmptyLookup = () => {
    setLookupSymbol(null);
    setLookupOpen(true);
  };

  return (
    <>
      {/* Search bar — standalone */}
      <div className="terminal-panel rounded-xl px-4 py-3 sm:px-5">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--muted)]">
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
              <path d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <button
            onClick={openEmptyLookup}
            className="flex-1 rounded-lg border border-dashed border-[var(--panel-border)] bg-transparent px-3 py-2 text-left text-sm text-[var(--muted)] transition-colors hover:border-[var(--terminal-accent)]/40 hover:text-[var(--foreground)]"
          >
            {locale === "EN"
              ? "Enter any stock ticker to view financial details..."
              : "Nhập mã cổ phiếu bất kỳ để xem chi tiết tài chính..."}
          </button>
        </div>
      </div>

      <section className="terminal-panel overflow-hidden rounded-xl">
        <div className="flex flex-col gap-2 border-b px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div>
            <h2 className="terminal-section-heading text-sm font-bold uppercase tracking-[0.18em]">
              {locale === "EN" ? "Ranked candidates" : "Xếp hạng mã"} ({displayCandidates.length})
            </h2>
            <p className="mt-0.5 text-[10px] text-[var(--muted)]">
              {locale === "EN"
                ? "Click any symbol to view full financial report"
                : "Nhấn vào mã để xem báo cáo tài chính chi tiết"}
            </p>
          </div>
          <label className="flex items-center gap-2 text-xs font-medium cursor-pointer select-none text-[var(--muted)]">
            <input
              type="checkbox"
              checked={filter100B}
              onChange={(e) => setFilter100B(e.target.checked)}
              className="h-4 w-4 rounded border-[var(--panel-border)] bg-[var(--surface-raised)] accent-[var(--terminal-accent)]"
            />
            <span>{locale === "EN" ? "Filter Cap ≥ 100B VND" : "Lọc vốn hoá ≥ 100 tỷ"}</span>
          </label>
        </div>
        {!isVIP ? (
          <LockedRows locale={locale} />
        ) : displayCandidates.length ? (
          <div className="w-full max-w-full">
            <div className="sm:hidden px-4 py-1.5 bg-[var(--surface-raised)] border-b text-[10px] font-mono text-[var(--muted)] flex items-center justify-between">
              <span>← {locale === "EN" ? "Swipe to view Close Price & Exchange" : "Vuốt ngang để xem Giá đóng cửa & Sàn"} →</span>
            </div>
            <div className="advisor-table overflow-x-auto max-w-full touch-pan-x">
              <div className="advisor-row advisor-row-head">
                <span>#</span>
                <span>{locale === "EN" ? "Symbol" : "Mã"}</span>
                <span>{locale === "EN" ? "Company Name" : "Tên công ty"}</span>
                <span>{locale === "EN" ? "Market Cap" : "Vốn hoá"}</span>
                <span>{locale === "EN" ? "Close Price" : "Giá đóng cửa"}</span>
                <span>{locale === "EN" ? "Exchange" : "Sàn giao dịch"}</span>
              </div>
              {displayCandidates.map((candidate, idx) => (
                <CandidateRow
                  key={candidate.symbol}
                  candidate={{ ...candidate, rank: idx + 1 }}
                  locale={locale}
                  onSymbolClick={openLookup}
                />
              ))}
            </div>
          </div>
        ) : (
          <LockedRows locale={locale} empty />
        )}
      </section>

      <StockLookupModal
        initialSymbol={lookupSymbol}
        isOpen={lookupOpen}
        onClose={() => setLookupOpen(false)}
      />
    </>
  );
}

function CandidateRow({
  candidate,
  locale,
  onSymbolClick,
}: {
  candidate: StockAdvisorCandidate;
  locale: "VN" | "EN";
  onSymbolClick: (symbol: string) => void;
}) {
  const companyName = getCompanyName(candidate.symbol);
  const marketCap = getMarketCap(candidate.symbol, locale);
  const exchange = candidate.exchange || getExchange(candidate.symbol);
  return (
    <div className="advisor-row">
      <span className="font-mono text-xs font-bold text-[var(--muted)]">{candidate.rank}</span>
      <span
        className="font-mono text-lg font-black text-[var(--foreground)] cursor-pointer underline decoration-dashed decoration-[var(--terminal-accent)]/40 underline-offset-2 hover:text-[var(--terminal-accent)] hover:decoration-[var(--terminal-accent)] transition-colors"
        onClick={() => onSymbolClick(candidate.symbol)}
      >
        {candidate.symbol}
      </span>
      <span className="font-sans text-xs text-[var(--muted)] font-medium truncate" title={companyName}>{companyName}</span>
      <span className="font-mono text-xs text-[var(--terminal-warning)] font-semibold">{marketCap}</span>
      <PriceCell price={candidate.close_price} changePct={candidate.price_change_pct} />
      <span>
        <span className="font-mono text-[11px] font-extrabold px-2 py-0.5 rounded border border-[var(--panel-border)] bg-[var(--surface-raised)] text-[var(--muted)]">
          {exchange}
        </span>
      </span>
    </div>
  );
}

function PriceCell({ price, changePct }: { price?: number; changePct?: number }) {
  if (!price || price <= 0) return <span className="text-[var(--muted)]">—</span>;
  const isPos = (changePct || 0) >= 0;
  const colorClass = isPos ? "text-[var(--terminal-accent)] font-semibold" : "text-[var(--terminal-danger)] font-semibold";
  const rawPct = changePct || 0;
  const displayPct = Math.abs(rawPct) <= 1.0 ? rawPct * 100 : rawPct;
  const pctStr = `${isPos ? "+" : ""}${displayPct.toFixed(1)}%`;
  return (
    <span className="font-mono text-xs">
      {price.toFixed(1)}{" "}
      <span className={`text-[11px] ${colorClass}`}>({pctStr})</span>
    </span>
  );
}

function LockedRows({ locale, empty = false }: { locale: "VN" | "EN"; empty?: boolean }) {
  const text = empty
    ? locale === "EN" ? "No symbol passed every gate." : "Không có mã vượt toàn bộ điều kiện."
    : locale === "EN" ? "VIP access is required to view symbols." : "Cần quyền VIP để xem danh sách mã.";
  return <div className="p-8 text-center text-sm text-[var(--muted)]">{text}</div>;
}
