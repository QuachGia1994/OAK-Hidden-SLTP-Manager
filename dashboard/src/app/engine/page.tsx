import { DashboardAutoRefresh } from "@/components/DashboardAutoRefresh";
import { Pattern5Board } from "@/components/Pattern5Board";
import { detectServerLocaleFromCookie } from "@/lib/i18n";
import { getLatestPattern5, getPattern5Profile, type Pattern5Payload } from "@/lib/pattern5";
import { getVipAccessState, redactPattern5Signals } from "@/lib/vip";
import { headers } from "next/headers";

export const dynamic = "force-dynamic";

const ACTIVE_PAIRS = new Set(["GBPUSD", "EURUSD"]);
const EUR_REFERENCE = new Set(["EURUSD"]);

function filterActivePairs(payload: Pattern5Payload | null) {
  return payload ? { ...payload, tables: payload.tables.filter((table) => ACTIVE_PAIRS.has(table.base)) } : null;
}

function mergeEurReference(primary: Pattern5Payload | null, reference: Pattern5Payload | null) {
  if (!primary || !reference || primary.weekStart !== reference.weekStart) return primary;
  const existing = new Set(primary.tables.map((table) => table.base));
  const extras = reference.tables
    .filter((table) => EUR_REFERENCE.has(table.base) && !existing.has(table.base))
    .map((table) => ({ ...table, sourceProfile: reference.profile }));
  return extras.length ? { ...primary, tables: [...primary.tables, ...extras] } : primary;
}

export default async function EnginePage() {
  const headerList = await headers();
  const locale = detectServerLocaleFromCookie(
    headerList.get("cookie"),
    headerList.get("accept-language"),
  );
  const cookieHeader = headerList.get("cookie") || "";
  const access = getVipAccessState(cookieHeader);
  const referenceProfile = process.env.PATTERN5_REFERENCE_PROFILE || "VantageDemo";
  const [primary, reference] = await Promise.all([
    getLatestPattern5(),
    getPattern5Profile(referenceProfile),
  ]);
  const rawData = mergeEurReference(filterActivePairs(primary), filterActivePairs(reference));
  const data = access.unlocked ? rawData : redactPattern5Signals(rawData);

  return (
    <div className="page-shell terminal-page">
      <DashboardAutoRefresh />
      <Pattern5Board data={data} locale={locale} access={access} />
    </div>
  );
}
