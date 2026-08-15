import { DashboardAutoRefresh } from "@/components/DashboardAutoRefresh";
import { Pattern5Board } from "@/components/Pattern5Board";
import { detectServerLocaleFromCookie } from "@/lib/i18n";
import { getLatestPattern5 } from "@/lib/pattern5";
import { getVipAccessState, redactPattern5Signals } from "@/lib/vip";
import { headers } from "next/headers";

export const dynamic = "force-dynamic";

export default async function EnginePage() {
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(
    headerList.get("cookie"),
    headerList.get("accept-language"),
  );
  const cookieHeader = headerList.get("cookie") || "";
  const access = getVipAccessState(cookieHeader);
  const rawData = await getLatestPattern5();
  const data = access.unlocked ? rawData : redactPattern5Signals(rawData);

  return (
    <div className="page-shell terminal-page">
      <DashboardAutoRefresh />
      <Pattern5Board data={data} locale={locale} access={access} />
    </div>
  );
}
