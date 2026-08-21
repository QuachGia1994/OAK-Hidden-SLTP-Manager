import { DashboardAutoRefresh } from "@/components/DashboardAutoRefresh";
import { H1EngineBoard } from "@/components/H1EngineBoard";
import { detectServerLocaleFromCookie } from "@/lib/i18n";
import { getLatestH1Signals, maskFutureH1Signals } from "@/lib/h1-signals";
import { getVipAccessState, redactH1Signals } from "@/lib/vip";
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
  const rawH1Data = maskFutureH1Signals(await getLatestH1Signals());
  const h1Data = access.unlocked ? rawH1Data : redactH1Signals(rawH1Data);

  return (
    <div className="page-shell terminal-page">
      <DashboardAutoRefresh />
      <H1EngineBoard h1Data={h1Data} locale={locale} access={access} />
    </div>
  );
}
