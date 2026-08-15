import { DashboardAutoRefresh } from "@/components/DashboardAutoRefresh";
import { Pattern5Board } from "@/components/Pattern5Board";
import { detectServerLocaleFromCookie } from "@/lib/i18n";
import { getLatestPattern5 } from "@/lib/pattern5";
import { headers } from "next/headers";

export const dynamic = "force-dynamic";

export default async function EnginePage() {
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(
    headerList.get("cookie"),
    headerList.get("accept-language"),
  );
  const data = await getLatestPattern5();

  return (
    <div className="page-shell terminal-page">
      <DashboardAutoRefresh />
      <Pattern5Board data={data} locale={locale} />
    </div>
  );
}
