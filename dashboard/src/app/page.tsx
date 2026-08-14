import { TradeAuditDashboard } from "@/components/TradeAuditDashboard";
import { detectServerLocaleFromCookie } from "@/lib/i18n";
import { hasVipAccess } from "@/lib/vip";
import { headers } from "next/headers";

export const dynamic = "force-dynamic";

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<{ vip?: string; account?: string }>;
}) {
  const params = await searchParams;
  const isVIP = await hasVipAccess(params);
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(
    headerList.get("cookie"),
    headerList.get("accept-language"),
  );

  return (
    <div className="page-shell terminal-page space-y-5">
      <TradeAuditDashboard
        locale={locale}
        accountId={params.account ?? null}
        isVIP={isVIP}
      />
    </div>
  );
}
