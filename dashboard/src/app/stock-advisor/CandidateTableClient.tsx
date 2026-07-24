"use client";

import { useState } from "react";
import { getCompanyName, getMarketCap } from "@/lib/stock-names";
import type { StockAdvisorCandidate } from "@/lib/types";

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

  const displayCandidates = filter100B
    ? candidates.filter((c) => {
        const cap = getMarketCap(c.symbol, locale);
        return !cap.includes("nhỏ") && !cap.includes("<");
      })
    : candidates;

  return (
    <section className="terminal-panel overflow-hidden rounded-xl">
      <div className="flex flex-col gap-2 border-b px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-5">
        <h2 className="terminal-section-heading text-sm font-bold uppercase tracking-[0.18em]">
          {locale === "EN" ? "Ranked candidates" : "Xếp hạng mã"} ({displayCandidates.length})
        </h2>
        <label className="flex items-center gap-2 text-xs text-zinc-300 font-medium cursor-pointer select-none">
          <input
            type="checkbox"
            checked={filter100B}
            onChange={(e) => setFilter100B(e.target.checked)}
            className="h-4 w-4 rounded border-zinc-700 bg-zinc-900 text-amber-500 focus:ring-amber-500"
          />
          <span>{locale === "EN" ? "Filter Cap ≥ 100B VND" : "Lọc vốn hoá ≥ 100 tỷ"}</span>
        </label>
      </div>
      {!isVIP ? (
        <LockedRows locale={locale} />
      ) : displayCandidates.length ? (
        <div className="advisor-table overflow-x-auto">
          <div className="advisor-row advisor-row-head">
            <span>#</span>
            <span>{locale === "EN" ? "Symbol" : "Mã"}</span>
            <span>{locale === "EN" ? "Company Name" : "Tên công ty"}</span>
            <span>{locale === "EN" ? "Market Cap" : "Vốn hoá"}</span>
            <span>{locale === "EN" ? "Close Price" : "Giá đóng cửa"}</span>
            <span>EDGE *</span>
          </div>
          {displayCandidates.map((candidate, idx) => (
            <CandidateRow key={candidate.symbol} candidate={{ ...candidate, rank: idx + 1 }} locale={locale} />
          ))}
          <div className="border-t px-4 py-2.5 text-[11px] text-zinc-400 dark:text-zinc-500">
            * EDGE: {locale === "EN" ? "Expected excess return (Alpha) over benchmark on D1 signal." : "Tỷ suất sinh lời kỳ vọng vượt trội (Alpha) của cổ phiếu khi xuất hiện tín hiệu D1."}
          </div>
        </div>
      ) : (
        <LockedRows locale={locale} empty />
      )}
    </section>
  );
}

function CandidateRow({ candidate, locale }: { candidate: StockAdvisorCandidate; locale: "VN" | "EN" }) {
  const companyName = getCompanyName(candidate.symbol);
  const marketCap = getMarketCap(candidate.symbol, locale);
  return (
    <div className="advisor-row">
      <span className="text-zinc-400">{candidate.rank}</span>
      <span className="font-mono text-lg font-black">{candidate.symbol}</span>
      <span className="font-sans text-xs text-zinc-300 font-medium truncate" title={companyName}>{companyName}</span>
      <span className="font-mono text-xs text-amber-400/90 font-semibold">{marketCap}</span>
      <PriceCell price={candidate.close_price} changePct={candidate.price_change_pct} />
      <span>{formatPercent(candidate.conditional_edge)}</span>
    </div>
  );
}

function PriceCell({ price, changePct }: { price?: number; changePct?: number }) {
  if (!price || price <= 0) return <span className="text-zinc-500">—</span>;
  const isPos = (changePct || 0) >= 0;
  const colorClass = isPos ? "text-emerald-400 font-semibold" : "text-rose-400 font-semibold";
  const pctStr = changePct !== undefined ? `${isPos ? "+" : ""}${(changePct * 100).toFixed(1)}%` : "0.0%";
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
  return <div className="p-8 text-center text-sm text-zinc-500">{text}</div>;
}

function formatPercent(value: number): string {
  return `${(Number(value || 0) * 100).toFixed(1)}%`;
}
