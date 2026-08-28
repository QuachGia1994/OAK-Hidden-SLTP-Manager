import { H1EngineBoard } from "@/components/H1EngineBoard";
import { detectServerLocaleFromCookie } from "@/lib/i18n";
import { readLatestH1Signals } from "@/lib/h1-signals";
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
  const read = await readLatestH1Signals();
  const h1Data = read.ok ? (access.unlocked ? read.data : redactH1Signals(read.data)) : null;

  return (
    <div className="page-shell terminal-page">
      <H1EngineBoard h1Data={h1Data} degraded={read.ok === false} locale={locale} access={access} />
    </div>
  );
}
