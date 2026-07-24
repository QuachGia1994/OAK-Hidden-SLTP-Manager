import { DashboardAutoRefresh } from "@/components/DashboardAutoRefresh";
import { getStockAdvisory, maskStockAdvisory } from "@/lib/data";
import { DashboardAutoRefresh } from "@/components/DashboardAutoRefresh";
import { getStockAdvisory, maskStockAdvisory } from "@/lib/data";
import { detectServerLocaleFromCookie } from "@/lib/i18n";
import { localizeAdvisorWarning } from "@/lib/stock-advisor-i18n";
import type { StockAdvisory, StockAdvisorCandidate } from "@/lib/types";
import { hasVipAccess } from "@/lib/vip";
import { headers } from "next/headers";
import { getCompanyName } from "@/lib/stock-names";

export const dynamic = "force-dynamic";

export default async function StockAdvisorPage({ searchParams }: { searchParams: Promise<{ vip?: string }> }) {
  const params = await searchParams;
  const [advisory, isVIP, headerList] = await Promise.all([
    getStockAdvisory(),
    hasVipAccess(params),
    headers(),
  ]);
  const locale = detectServerLocaleFromCookie(headerList.get("cookie"), headerList.get("accept-language"));
  const visible = advisory && !isVIP ? maskStockAdvisory(advisory) : advisory;
  return (
    <div className="page-shell terminal-page space-y-5">
      <DashboardAutoRefresh />
      <AdvisorHero advisory={visible} locale={locale} isVIP={isVIP} />
      {visible ? <AdvisorResult advisory={visible} locale={locale} isVIP={isVIP} /> : <AdvisorEmpty locale={locale} />}
    </div>
  );
}

function AdvisorHero({ advisory, locale, isVIP }: { advisory: StockAdvisory | null; locale: "VN" | "EN"; isVIP: boolean }) {
  const direction = advisory?.signal.direction || "—";
  const directionTone = direction === "BUY" ? "text-[var(--terminal-accent-strong)]" : direction === "SELL" ? "text-red-500" : "text-zinc-500";
  const directionText = locale === "EN" ? direction : direction === "BUY" ? "MUA" : direction === "SELL" ? "BÁN" : direction;
  const status = advisory?.status || "EMPTY";
  const accessText = locale === "EN" ? (isVIP ? "OPEN" : "LOCKED") : (isVIP ? "ĐÃ MỞ" : "ĐÃ KHÓA");
  return (
    <section className="terminal-hero rounded-2xl px-5 py-6 sm:px-7 sm:py-7">
      <div className="relative grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,0.8fr)] lg:items-end">
        <div>
          <h1 className="text-4xl font-black tracking-tight text-zinc-950 dark:text-white sm:text-5xl">
            {locale === "EN" ? "VN Stock Filter" : "Bộ lọc Cổ phiếu"}
          </h1>
          <p className="mt-2 max-w-2xl text-sm text-zinc-500 dark:text-zinc-400">
            {locale === "EN" ? "H4 similarity · 25 completed sessions · HOSE, HNX, UPCoM (Cap ≥ 100B VND)" : "Tuyến tính H4 · 25 phiên hoàn tất · HOSE, HNX, UPCoM (Vốn hoá ≥ 100 tỷ)"}
          </p>
        </div>
        <div className="grid grid-cols-3 gap-2 sm:gap-3">
          <HeroStat label={locale === "EN" ? "STATUS" : "TRẠNG THÁI"} value={localizeAdvisorStatus(status, locale)} />
          <HeroStat label={locale === "EN" ? "H4" : "MỐC H4"} value={directionText} valueClass={directionTone} />
          <HeroStat label={locale === "EN" ? "ACCESS" : "QUYỀN XEM"} value={accessText} />
        </div>
      </div>
    </section>
  );
}

function AdvisorResult({ advisory, locale, isVIP }: { advisory: StockAdvisory; locale: "VN" | "EN"; isVIP: boolean }) {
  return (
    <>
      <SafetyStrip advisory={advisory} locale={locale} />
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.65fr)_minmax(19rem,0.7fr)]">
        <CandidateTable advisory={advisory} locale={locale} isVIP={isVIP} />
        <EvidencePanel advisory={advisory} locale={locale} />
      </div>
    </>
  );
}

function SafetyStrip({ advisory, locale }: { advisory: StockAdvisory; locale: "VN" | "EN" }) {
  const action = advisory.action === "BUY_OR_HOLD" ? "BUY / HOLD" : "SELL / AVOID";
  return (
    <section className="advisor-safety grid gap-3 rounded-xl border px-4 py-4 sm:grid-cols-[auto_1fr_auto] sm:items-center sm:px-5">
      <div className="font-mono text-xl font-black">{action}</div>
      <p className="text-sm text-zinc-600 dark:text-zinc-300">
        {locale === "EN" ? "User confirmation is required before every real trade." : "User phải xác nhận trước mọi giao dịch thật."}
      </p>
      <span className="rounded-md border border-amber-400/30 bg-amber-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase text-amber-500">
        {locale === "EN" ? "No order submitted" : "Không gửi lệnh"}
      </span>
    </section>
  );
}

function CandidateTable({ advisory, locale, isVIP }: { advisory: StockAdvisory; locale: "VN" | "EN"; isVIP: boolean }) {
  return (
    <section className="terminal-panel overflow-hidden rounded-xl">
      <div className="border-b px-4 py-4 sm:px-5">
        <h2 className="terminal-section-heading text-sm font-bold uppercase tracking-[0.18em]">
          {locale === "EN" ? "Ranked candidates" : "Xếp hạng mã"}
        </h2>
      </div>
      {!isVIP ? <LockedRows locale={locale} /> : advisory.candidates.length ? (
        <div className="advisor-table">
          <div className="advisor-row advisor-row-head">
            <span>#</span>
            <span>{locale === "EN" ? "Symbol" : "Mã"}</span>
            <span>{locale === "EN" ? "Company Name" : "Tên công ty"}</span>
            <span>{locale === "EN" ? "Weight" : "Tỷ trọng"}</span>
            <span>{locale === "EN" ? "Hit H4" : "Khớp H4"}</span>
            <span>EDGE</span>
          </div>
          {advisory.candidates.map((candidate) => <CandidateRow key={candidate.symbol} candidate={candidate} locale={locale} />)}
        </div>
      ) : <LockedRows locale={locale} empty />}
    </section>
  );
}

function CandidateRow({ candidate, locale }: { candidate: StockAdvisorCandidate; locale: "VN" | "EN" }) {
  const companyName = getCompanyName(candidate.symbol);
  return (
    <div className="advisor-row">
      <span className="text-zinc-400">{candidate.rank}</span>
      <span className="font-mono text-lg font-black">{candidate.symbol}</span>
      <span className="font-sans text-xs text-zinc-300 font-medium truncate" title={companyName}>{companyName}</span>
      <span>{formatPercent(candidate.weight)}</span>
      <span>{formatPercent(candidate.conditional_hit_rate)}</span>
      <span>{formatPercent(candidate.conditional_edge)}</span>
    </div>
  );
}

function EvidencePanel({ advisory, locale }: { advisory: StockAdvisory; locale: "VN" | "EN" }) {
  const backtest = advisory.backtest;
  return (
    <section className="terminal-panel rounded-xl p-4 sm:p-5">
      <h2 className="terminal-section-heading text-sm font-bold uppercase tracking-[0.18em]">
        {locale === "EN" ? "Evidence" : "Độ tin cậy"}
      </h2>
      <dl className="mt-4 grid gap-3">
        <EvidenceRow label={locale === "EN" ? "Signal date" : "Ngày signal"} value={advisory.signal.date} />
        <EvidenceRow label={locale === "EN" ? "Evaluated" : "Đã đánh giá"} value={`${backtest.evaluated_decisions}/${backtest.requested_decisions}`} />
        <EvidenceRow label="Hit rate" value={formatPercent(backtest.hit_rate)} />
        <EvidenceRow label={locale === "EN" ? "Cash reserve" : "Tiền mặt"} value={formatPercent(advisory.cash_weight)} />
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
