import { H1SignalBoard } from "@/components/H1SignalBoard";
import { detectServerLocaleFromCookie } from "@/lib/i18n";
import { readLatestH1Signals } from "@/lib/h1-signals";
import { getVipAccessState, redactH1Signals } from "@/lib/vip";
import { headers } from "next/headers";

export const dynamic = "force-dynamic";

export default async function HistoryPage() {
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(
    headerList.get("cookie"),
    headerList.get("accept-language"),
  );
  const cookieHeader = headerList.get("cookie") || "";
  const access = getVipAccessState(cookieHeader);
  const read = await readLatestH1Signals();
  const data = read.ok ? (access.unlocked ? read.data : redactH1Signals(read.data)) : null;

  return (
    <div className="page-shell terminal-page oak-history-page">
      <header className="oak-history-page-head">
        <span className="oak-eyebrow">TRADING / HISTORY</span>
        <h1>{locale === "EN" ? "H1 History" : "Lịch sử H1"}</h1>
        <p>{locale === "EN" ? "Browse retained broker days without leaving the history workspace." : "Xem lại các ngày broker đã lưu mà không cần quay về màn hình live."}</p>
      </header>
      <H1SignalBoard data={data} degraded={read.ok === false} locale={locale} unlocked={access.unlocked} mode="history" />
    </div>
  );
}
