import { WorkspaceHeading } from "@/components/WorkspaceHeading";
import { H1SignalBoard } from "@/components/H1SignalBoard";
import { detectServerLocaleFromCookie } from "@/lib/i18n";
import { readLatestH1Signals } from "@/lib/h1-signals";
import { headers } from "next/headers";

export const dynamic = "force-dynamic";

export default async function HistoryPage() {
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(
    headerList.get("cookie"),
    headerList.get("accept-language"),
  );
  const read = await readLatestH1Signals();
  const data = read.ok ? read.data : null;

  return (
    <div className="page-shell terminal-page oak-history-page">
      <WorkspaceHeading workspace="history" locale={locale} />
      <H1SignalBoard data={data} degraded={read.ok === false} locale={locale} mode="history" />
    </div>
  );
}
