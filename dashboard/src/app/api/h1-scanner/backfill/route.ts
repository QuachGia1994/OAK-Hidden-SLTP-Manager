import { NextResponse } from "next/server";
import { requireAdminOrApiAuth } from "@/lib/admin-auth";
import { brokerWallParts, fetchHistoricalBrokerH1 } from "@/lib/ctrader-json";
import { verifyH1ScannerGitHubOidc } from "@/lib/github-oidc";
import { addBrokerCalendarDays, brokerDateWeekdayIndex } from "@/lib/h1-broker-date";
import { H1_HISTORY_RETENTION_CALENDAR_DAYS, H1_SCAN_END_HOUR } from "@/lib/h1-cloud-scanner";
import { acquireH1CloudLock, loadH1CloudHistoryState, publishH1CloudState, releaseH1CloudLock, saveH1CloudState } from "@/lib/h1-cloud-store";
import { loadH1CTraderSession } from "@/lib/h1-ctrader-session";
import { mergeHistoricalBackfill, reconstructHistoricalDays } from "@/lib/h1-history-backfill";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
export const maxDuration = 180;

function utcHistoryEnvelopeStart(dateKey: string): number {
  return Date.parse(`${dateKey}T00:00:00Z`) - 4 * 3_600_000;
}

function requestedWeekdays(fromDate: string, throughDate: string): string[] {
  const dates: string[] = [];
  for (let date = fromDate; date <= throughDate; date = addBrokerCalendarDays(date, 1)) {
    const weekday = brokerDateWeekdayIndex(date);
    if (weekday >= 1 && weekday <= 5) dates.push(date);
  }
  return dates;
}

async function authorize(request: Request): Promise<NextResponse | null> {
  const denied = requireAdminOrApiAuth(request);
  if (!denied) return null;
  const header = request.headers.get("authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  if (token && await verifyH1ScannerGitHubOidc(token)) return null;
  return denied;
}

export async function POST(request: Request) {
  const denied = await authorize(request);
  if (denied) return denied;

  const url = new URL(request.url);
  if (url.searchParams.has("days") || url.searchParams.has("from") || url.searchParams.has("to")) {
    return NextResponse.json({ ok: false, error: "H1 history backfill uses the fixed 90-calendar-day window." }, { status: 400 });
  }

  const lockToken = await acquireH1CloudLock();
  if (!lockToken) return NextResponse.json({ ok: true, skipped: "already-running" }, { headers: { "Cache-Control": "no-store" } });

  try {
    const nowMs = Date.now();
    const current = brokerWallParts(nowMs);
    const requestedFrom = addBrokerCalendarDays(current.dateKey, -(H1_HISTORY_RETENTION_CALENDAR_DAYS - 1));
    const { state, source } = await loadH1CloudHistoryState();
    const recoverMissingCurrentDay = current.hour > H1_SCAN_END_HOUR && !state.days[current.dateKey];
    const requestedThrough = recoverMissingCurrentDay ? current.dateKey : addBrokerCalendarDays(current.dateKey, -1);
    const session = await loadH1CTraderSession();
    const startedAt = Date.now();
    const historical = await fetchHistoricalBrokerH1(session, utcHistoryEnvelopeStart(requestedFrom), nowMs, {
      deadlineMs: startedAt + 150_000,
    });
    const reconstructedAll = reconstructHistoricalDays(historical.symbols);
    const reconstructed = Object.fromEntries(Object.entries(reconstructedAll).filter(([date]) =>
      date >= requestedFrom && (date < current.dateKey || (recoverMissingCurrentDay && date === current.dateKey)),
    ));
    const coverageDates = Object.keys(reconstructed).sort();
    const coverageSet = new Set(coverageDates);
    const unavailableWeekdays = requestedWeekdays(requestedFrom, requestedThrough).filter((date) => !coverageSet.has(date));
    const merged = mergeHistoricalBackfill(state, reconstructed, current.dateKey, { includeMissingCurrentDay: recoverMissingCurrentDay });

    if (merged.addedAlerts > 0 || merged.addedDays > 0) {
      await saveH1CloudState(state);
      await publishH1CloudState(state);
    }

    return NextResponse.json({
      ok: true,
      retentionCalendarDays: H1_HISTORY_RETENTION_CALENDAR_DAYS,
      requestedFrom,
      requestedThrough,
      currentBrokerDate: current.dateKey,
      recoveredMissingCurrentDay: recoverMissingCurrentDay && Boolean(state.days[current.dateKey]),
      stateSource: source,
      providerRequestCount: historical.requestCount,
      providerBarCounts: Object.fromEntries(Object.entries(historical.symbols).map(([base, item]) => [base, item.bars.filter((bar) =>
        bar.brokerDate >= requestedFrom && (bar.brokerDate < current.dateKey || (recoverMissingCurrentDay && bar.brokerDate === current.dateKey)),
      ).length])),
      availableTradingDays: coverageDates.length,
      earliestAvailableDate: coverageDates[0] || null,
      latestAvailableDate: coverageDates.at(-1) || null,
      unavailableWeekdays,
      addedDays: merged.addedDays,
      addedAlerts: merged.addedAlerts,
    }, { headers: { "Cache-Control": "no-store, max-age=0" } });
  } catch (error) {
    console.error("[H1 HISTORY BACKFILL]", { status: "failed", errorClass: error instanceof Error ? error.name : "UnknownError" });
    return NextResponse.json({ ok: false, error: "H1 history backfill failed." }, { status: 502, headers: { "Cache-Control": "no-store, max-age=0" } });
  } finally {
    await releaseH1CloudLock(lockToken);
  }
}
