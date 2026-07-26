import { DashboardAutoRefresh } from "@/components/DashboardAutoRefresh";
import { getStockAdvisory, maskStockAdvisory } from "@/lib/data";
import { detectServerLocaleFromCookie } from "@/lib/i18n";
import type { StockAdvisory } from "@/lib/types";
import { hasVipAccess } from "@/lib/vip";
import { headers } from "next/headers";
import { CandidateTableClient } from "./CandidateTableClient";

export const dynamic = "force-dynamic";

export default async function StockAdvisorPage({ searchParams }: { searchParams: Promise<{ vip?: string }> }) {
  const params = await searchParams;
  const [advisory, isVIP, headerList] = await Promise.all([
    getStockAdvisory(),
    hasVipAccess(params),
    headers(),
  ]);
  const locale = detectServerLocaleFromCookie(headerList.get("cookie"));
  const maskedAdvisory = advisory && !isVIP ? maskStockAdvisory(advisory) : advisory;

  // Prevent CDN from caching VIP-gated responses across day boundaries
  const { cookies } = await import("next/headers");
  const resHeaders = new Headers();
  resHeaders.set("Cache-Control", "no-store, must-revalidate");

  return (
    <div className="space-y-6">
      <DashboardAutoRefresh />
      {maskedAdvisory ? (
        <>
          <AdvisorHeader advisory={maskedAdvisory} locale={locale} isVIP={isVIP} />
          <AdvisorResult advisory={maskedAdvisory} locale={locale} isVIP={isVIP} />
        </>
      ) : (
        <AdvisorEmpty locale={locale} />
      )}
    </div>
  );
}

function AdvisorHeader({ advisory, locale, isVIP }: { advisory: StockAdvisory; locale: "VN" | "EN"; isVIP: boolean }) {
  const statusLabel = advisory.status === "READY"
    ? locale === "EN" ? "READY" : "SẴN SÀNG"
    : advisory.status === "PARTIAL"
    ? locale === "EN" ? "PARTIAL" : "BỘ PHẬN"
    : locale === "EN" ? "NO TRADE" : "KHÔNG MUA";

  const actionLabel = advisory.action === "BUY_OR_HOLD"
    ? locale === "EN" ? "BUY" : "MUA"
    : locale === "EN" ? "AVOID" : "TRÁNH";

  const statusColor = advisory.status === "READY"
    ? "text-[var(--terminal-accent)] font-bold"
    : advisory.status === "PARTIAL"
    ? "text-[var(--terminal-warning)] font-bold"
    : "text-[var(--terminal-danger)] font-bold";

  return (
    <div className="terminal-panel rounded-xl p-5 sm:p-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="terminal-title text-2xl font-black tracking-tight sm:text-3xl">
            {locale === "EN" ? "Stock Filter" : "Bộ lọc Cổ phiếu"}
          </h1>
          <p className="terminal-subtitle mt-1 text-xs text-zinc-400 sm:text-sm">
            {locale === "EN"
              ? "Linear D1 · 25 completed sessions · HOSE, HNX, UPCoM (Cap ≥ 100B VND)"
              : "Tuyến tính D1 · 25 phiên hoàn tất · HOSE, HNX, UPCoM (Vốn hoá ≥ 100 tỷ)"}
          </p>
        </div>
        <div className="grid grid-cols-3 gap-2 sm:gap-3">
          <HeroStat label={locale === "EN" ? "STATUS" : "TRẠNG THÁI"} value={statusLabel} valueClass={statusColor} />
          <HeroStat label={locale === "EN" ? "SIGNAL D1" : "MỐC D1"} value={actionLabel} valueClass="text-[var(--terminal-accent-strong)] font-bold" />
          <HeroStat label={locale === "EN" ? "ACCESS" : "QUYỀN XEM"} value={isVIP ? (locale === "EN" ? "UNLOCKED" : "ĐÃ MỞ") : (locale === "EN" ? "LOCKED" : "KHÓA")} valueClass={isVIP ? "text-[var(--terminal-accent)]" : "text-[var(--terminal-warning)]"} />
        </div>
      </div>
    </div>
  );
}

function AdvisorResult({ advisory, locale, isVIP }: { advisory: StockAdvisory; locale: "VN" | "EN"; isVIP: boolean }) {
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.65fr)_minmax(19rem,0.7fr)]">
      <CandidateTableClient candidates={advisory.candidates} locale={locale} isVIP={isVIP} />
      <EvidencePanel advisory={advisory} locale={locale} />
    </div>
  );
}

function EvidencePanel({ advisory, locale }: { advisory: StockAdvisory; locale: "VN" | "EN" }) {
  const backtest = advisory.backtest;
  const sessionsVal = locale === "EN" ? `${backtest.evaluated_decisions}/${backtest.requested_decisions} sessions` : `${backtest.evaluated_decisions}/${backtest.requested_decisions} phiên`;
  return (
    <section className="terminal-panel rounded-xl p-4 sm:p-5">
      <h2 className="terminal-section-heading text-sm font-bold uppercase tracking-[0.18em]">
        {locale === "EN" ? "Evidence" : "Độ tin cậy"}
      </h2>
      <dl className="mt-4 grid gap-3">
        <EvidenceRow label={locale === "EN" ? "Signal date" : "Ngày signal"} value={advisory.signal.date} />
        <EvidenceRow label={locale === "EN" ? "Backtest sessions" : "Phiên kiểm định (Backtest)"} value={sessionsVal} />
        <EvidenceRow label="Hit rate" value={formatPercent(backtest.hit_rate)} />
        <EvidenceRow label={locale === "EN" ? "Rejected" : "Loại"} value={advisory.rejected_symbols.toString()} />
      </dl>
    </section>
  );
}

function EvidenceRow({ label, value }: { label: string; value: string }) {
  return <div className="flex items-center justify-between gap-4 border-b pb-2"><dt className="text-xs text-zinc-500">{label}</dt><dd className="font-mono text-sm font-bold">{value}</dd></div>;
}

function HeroStat({ label, value, valueClass = "" }: { label: string; value: string; valueClass?: string }) {
  return <div className="terminal-stat min-w-0 rounded-xl px-3 py-3"><div className="terminal-kicker mb-1 truncate">{label}</div><div className={`truncate font-mono text-base font-black sm:text-xl ${valueClass}`}>{value}</div></div>;
}

function LockedRows({ locale, empty = false }: { locale: "VN" | "EN"; empty?: boolean }) {
  const text = empty
    ? locale === "EN" ? "No symbol passed every gate." : "Không có mã vượt toàn bộ điều kiện."
    : locale === "EN" ? "VIP access is required to view symbols." : "Cần quyền VIP để xem danh sách mã.";
  return <div className="p-8 text-center text-sm text-zinc-500">{text}</div>;
}

function AdvisorEmpty({ locale }: { locale: "VN" | "EN" }) {
  return <section className="terminal-panel rounded-xl p-8 text-center text-zinc-500">{locale === "EN" ? "Run VN30 Advisor from the desktop app to publish the first result." : "Chạy Bộ lọc VN30 trên app desktop để xuất kết quả đầu tiên."}</section>;
}

function localizeAdvisorStatus(status: string, locale: "VN" | "EN"): string {
  if (locale === "EN") return status;
  const labels: Record<string, string> = {
    EMPTY: "CHƯA CÓ",
    READY: "SẴN SÀNG",
    PARTIAL: "CHƯA ĐỦ 3 MÃ",
    NO_TRADE: "KHÔNG GIAO DỊCH",
  };
  return labels[status] || status;
}

function formatPercent(value: number): string { return `${(Number(value || 0) * 100).toFixed(1)}%`; }
function formatCapital(value: number, locale: "VN" | "EN"): string { return new Intl.NumberFormat(locale === "EN" ? "en-US" : "vi-VN", { maximumFractionDigits: 0 }).format(Number(value || 0)); }
