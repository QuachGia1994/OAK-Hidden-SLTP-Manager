import { DashboardAutoRefresh } from "@/components/DashboardAutoRefresh";
import { Pattern5Board } from "@/components/Pattern5Board";
import { detectServerLocaleFromCookie } from "@/lib/i18n";
import { getLatestH1Signals, maskFutureH1Signals } from "@/lib/h1-signals";
import { filterActivePattern5, getLatestPattern5, maskFuturePattern5 } from "@/lib/pattern5";
import { getVipAccessState, redactH1Signals, redactPattern5Signals } from "@/lib/vip";
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
  const [pattern5Raw, h1Raw] = await Promise.all([
    getLatestPattern5(),
    getLatestH1Signals(),
  ]);
  const rawData = maskFuturePattern5(filterActivePattern5(pattern5Raw));
  const rawH1Data = maskFutureH1Signals(h1Raw);
  const data = access.unlocked ? rawData : redactPattern5Signals(rawData);
  const h1Data = access.unlocked ? rawH1Data : redactH1Signals(rawH1Data);

  return (
    <div className="page-shell terminal-page">
      <DashboardAutoRefresh />
      <Pattern5Board data={data} h1Data={h1Data} locale={locale} access={access} />
    </div>
  );
}
