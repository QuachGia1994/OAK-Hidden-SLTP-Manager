import { InvestmentSimulator } from "@/components/InvestmentSimulator";
import { PublicAccountSelector } from "@/components/PublicAccountSelector";
import { getTradeAuditAll, listPublicAccounts } from "@/lib/trade-audit";
import { detectServerLocaleFromCookie } from "@/lib/i18n";
import { headers } from "next/headers";

export const dynamic = "force-dynamic";

export default async function SimulatorPage({ searchParams }: { searchParams: Promise<{ account?: string }> }) {
  const params = await searchParams;
  const accounts = await listPublicAccounts();
  const selected = params.account && accounts.some((account) => account.public_account_id === params.account)
    ? params.account
    : accounts[0]?.public_account_id || null;
  const data = selected ? await getTradeAuditAll(selected) : null;
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(headerList.get("cookie"), headerList.get("accept-language"));
  const overview = (data?.overview || {}) as Record<string, unknown>;
  const accountLabel = String(overview.alias || accounts.find((account) => account.public_account_id === selected)?.alias || "OAK Trader");
  const currency = String(overview.currency || "USD");

  return (
    <div className="page-shell terminal-page space-y-4">
      {accounts.length > 0 && (
        <div className="terminal-panel rounded-2xl p-4">
          <div className="mb-2 text-[10px] font-mono font-bold uppercase tracking-[0.18em] text-[var(--muted)]">
            {locale === "VN" ? "Tài khoản mô phỏng" : "Simulation account"}
          </div>
          <PublicAccountSelector locale={locale} accounts={accounts} selectedAccountId={selected} />
        </div>
      )}
      <InvestmentSimulator
        locale={locale}
        performance={(data?.performance || null) as Record<string, unknown> | null}
        currency={currency}
        accountLabel={accountLabel}
      />
    </div>
  );
}
