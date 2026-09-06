import { detectServerLocaleFromCookie } from "@/lib/i18n";
import { readLatestH1Signals } from "@/lib/h1-signals";
import { headers } from "next/headers";
import { HistoryClient } from "./HistoryClient";

export const dynamic = "force-dynamic";

export default async function HistoryPage() {
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(
    headerList.get("cookie"),
    headerList.get("accept-language"),
  );
  const read = await readLatestH1Signals();
  return <HistoryClient data={read.ok ? read.data : null} degraded={read.ok === false} locale={locale} />;
}
