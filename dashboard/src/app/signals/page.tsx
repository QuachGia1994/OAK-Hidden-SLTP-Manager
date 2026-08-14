import { PublicAccountSelector } from "@/components/PublicAccountSelector";
import { TradeLedger } from "@/components/TradeLedger";
import { getTradeAuditAll, listPublicAccounts } from "@/lib/trade-audit";
import { hasVipAccess } from "@/lib/vip";
import { headers } from "next/headers";
import { detectServerLocaleFromCookie } from "@/lib/i18n";

export const dynamic = "force-dynamic";

export default async function SignalsPage({ searchParams }: { searchParams: Promise<{ vip?: string; account?: string }> }) {
  const params = await searchParams;
  const isVIP = await hasVipAccess(params);
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(headerList.get("cookie"), headerList.get("accept-language"));
  const accounts = await listPublicAccounts();
  const requested = params.account && accounts.some((account) => account.public_account_id === params.account) ? params.account : null;
  const selected = requested || accounts[0]?.public_account_id || null;
  const auditData = selected ? await getTradeAuditAll(selected) : await getTradeAuditAll(null);
  const overview = (auditData.overview as Record<string, unknown> | null) || {};
  const performance = (auditData.performance as Record<string, unknown> | null) || {};
  const currency = String(overview.currency || "USD");
  const ledger = Array.isArray(auditData.ledger) ? auditData.ledger : [];
  return (
    <div className="page-shell terminal-page space-y-5">
      <section className="terminal-hero history-hero rounded-xl px-5 py-5 sm:px-6 sm:py-6">
        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(19rem,0.8fr)] lg:items-end">
          <div>
            <div className="terminal-kicker mb-3">{locale === "EN" ? "Verified account ledger" : "Sổ giao dịch đã xác thực"}</div>
            <h1 className="text-4xl font-black tracking-tight text-[var(--foreground)] sm:text-5xl">{locale === "EN" ? "Trade history" : "Lịch sử giao dịch"}</h1>
            <p className="mt-2 text-sm text-[var(--muted)]">{locale === "EN" ? "Closed-trade history from the selected public account" : "Lịch sử vị thế đã đóng của tài khoản công khai đang chọn"}</p>
            {accounts.length > 0 && <div className="mt-4 max-w-md"><div className="mb-2 text-[10px] font-mono font-bold uppercase tracking-[0.18em] text-[var(--muted)]">{locale === "VN" ? "Tài khoản công khai" : "Public account"}</div><PublicAccountSelector locale={locale} accounts={accounts} selectedAccountId={selected} /></div>}
          </div>
          <div className="grid grid-cols-2 gap-3">
            <HistoryStat label={locale === "EN" ? "Trades" : "Giao dịch"} value={String(performance.closed_trade_count ?? ledger.length)} />
            <HistoryStat label={locale === "EN" ? "Access" : "Quyền xem"} value={isVIP ? "VIP" : locale === "EN" ? "Public" : "Công khai"} />
          </div>
        </div>
      </section>
      <section className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <HistoryMetric label={locale === "EN" ? "Closed trades" : "Lệnh đã đóng"} value={String(performance.closed_trade_count ?? "—")} />
        <HistoryMetric label={locale === "EN" ? "Win rate" : "Tỷ lệ thắng"} value={performance.win_rate != null ? `${(Number(performance.win_rate) * 100).toFixed(2)}%` : "—"} />
        <HistoryMetric label={locale === "EN" ? "Realized P/L" : "Lãi/lỗ đã chốt"} value={performance.realized_pl != null ? `${currency} ${Number(performance.realized_pl).toFixed(2)}` : "—"} />
        <HistoryMetric label={locale === "EN" ? "Profit factor" : "Profit factor"} value={performance.profit_factor != null ? Number(performance.profit_factor).toFixed(2) : "—"} />
      </section>
      <section className="terminal-panel rounded-2xl p-5 sm:p-6">
        <h2 className="terminal-section-heading mb-4 text-xs font-mono font-bold uppercase tracking-[0.22em] text-[var(--muted)]">{locale === "EN" ? "Trade history" : "Lịch sử giao dịch"}</h2>
        <TradeLedger data={ledger} locale={locale} currency={currency} emptyText={locale === "EN" ? "No closed trades in this account" : "Tài khoản chưa có giao dịch đã đóng"} maxRows={10} />
      </section>
    </div>
  );
}

function HistoryMetric({ label, value }: { label: string; value: string }) {
  return <div className="terminal-stat rounded-xl px-4 py-3"><div className="terminal-kicker mb-1">{label}</div><div className="terminal-stat-value font-mono text-lg font-black tabular-nums">{value}</div></div>;
}

function HistoryStat({ label, value }: { label: string; value: string }) {
  return <div className="terminal-stat rounded-lg px-4 py-3"><div className="terminal-kicker mb-1">{label}</div><div className="terminal-stat-value font-mono text-xl font-black">{value}</div></div>;
}
