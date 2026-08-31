import { createHash, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { redis, requireAuth } from "@/lib/redis-core";
import { loadH1CloudConfig } from "@/lib/h1-cloud-config";
import { verifyH1ScannerGitHubOidc } from "@/lib/github-oidc";
import { brokerWallParts, fetchCurrentBrokerDayMarket, type CTraderScannerSession } from "@/lib/ctrader-json";
import { loadH1CTraderSession } from "@/lib/h1-ctrader-session";
import { acquireH1CloudLock, loadH1CloudState, publishH1CloudState, releaseH1CloudLock, saveH1CloudState } from "@/lib/h1-cloud-store";
import {
  H1_FIRST_SCAN_HOUR,
  H1_SCAN_HOURS,
  H1_SIGNAL_END_HOUR,
  H1_TARGET_BASES,
  backfillSuppressedHistory,
  buildStoredAlert,
  ensureSymbolDay,
  evaluateH1SignalsForTarget,
  isH1SlotActiveForBrokerDate,
  targetsForBlockHour,
  type H1CloudState,
  type H1StoredAlert,
} from "@/lib/h1-cloud-scanner";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const RUN_TICKET_HEADER = "x-h1-run-ticket";
const RUN_TICKET_PREFIX = "oak:h1:run-ticket:";
const CF_TIMEKEEPER_TOKEN_HASH_KEY = "robot-sltp:cloud:h1-scanner:cf-timekeeper:sha256";
const CF_TIMEKEEPER_HEADER = "x-h1-timekeeper-key";
const FINALIZE_RETRY_ATTEMPTS = 8;
const FINALIZE_RETRY_DELAY_MS = 2_500;

type RunSummary = {
  base: string;
  slotHour: number;
  signal: string;
  postSignalRule: string;
};

function safeHexEqual(left: string, right: string): boolean {
  if (!/^[a-f0-9]{64}$/i.test(left) || !/^[a-f0-9]{64}$/i.test(right)) return false;
  return timingSafeEqual(Buffer.from(left, "hex"), Buffer.from(right, "hex"));
}

async function authorize(request: Request): Promise<NextResponse | null> {
  // Existing server-to-server API auth remains available for manual/admin runs.
  const apiDenied = requireAuth(request);
  if (!apiDenied) return null;

  // Cloudflare primary timekeeper uses a dedicated bearer known only to the
  // Worker. Vercel stores only its SHA-256 in Upstash, never the plaintext.
  const cfToken = request.headers.get(CF_TIMEKEEPER_HEADER) || "";
  if (/^[A-Za-z0-9_-]{40,120}$/.test(cfToken)) {
    const expectedHash = await redis.get<string>(CF_TIMEKEEPER_TOKEN_HASH_KEY);
    const actualHash = createHash("sha256").update(cfToken).digest("hex");
    if (typeof expectedHash === "string" && safeHexEqual(actualHash, expectedHash)) return null;
  }

  // Scheduled fallback runs use GitHub Actions OIDC; no scanner secret is stored in GitHub.
  const header = request.headers.get("authorization") || "";
  const token = header.startsWith("Bearer ") ? header.slice(7).trim() : "";
  if (token && await verifyH1ScannerGitHubOidc(token)) return null;

  // One-time local bootstrap ticket for dry-run/cutover verification. It is
  // consumed atomically and cannot become a standing service credential.
  const ticket = request.headers.get(RUN_TICKET_HEADER) || "";
  if (/^[A-Za-z0-9_-]{40,80}$/.test(ticket)) {
    const consumed = await redis.getdel<string>(`${RUN_TICKET_PREFIX}${ticket}`);
    if (consumed) return null;
  }
  return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function marketReadyForSlot(
  market: Awaited<ReturnType<typeof fetchCurrentBrokerDayMarket>>,
  brokerHour: number,
) {
  // The signal for slot S needs the S:00 H1 candle closed, i.e. broker hour S+1.
  const slotHour = brokerHour - 1;
  if (!isH1SlotActiveForBrokerDate(market.brokerDate, slotHour)) return true;
  if (!(targetsForBlockHour(slotHour) as readonly string[]).length) return false;
  return targetsForBlockHour(slotHour).every((base) =>
    market.symbols[base].bars.some((bar) => bar.hour === slotHour),
  );
}

async function fetchReadyMarket(session: CTraderScannerSession, nowMs: number, brokerHour: number) {
  let market = await fetchCurrentBrokerDayMarket(session, nowMs);
  for (let attempt = 1; attempt < FINALIZE_RETRY_ATTEMPTS && !marketReadyForSlot(market, brokerHour); attempt += 1) {
    await delay(FINALIZE_RETRY_DELAY_MS);
    market = await fetchCurrentBrokerDayMarket(session, Date.now());
  }
  return market;
}

function deliveredSlots(alerts: H1StoredAlert[]): Set<number> {
  return new Set(alerts.filter((item) => Number.isInteger(item.slotHour)).map((item) => item.slotHour));
}

export async function POST(request: Request) {
  const denied = await authorize(request);
  if (denied) return denied;

  const url = new URL(request.url);
  const dryRun = url.searchParams.get("dryRun") === "1";
  const cloudConfig = await loadH1CloudConfig();
  const enabled = Boolean(cloudConfig?.enabled);

  // Table/history publication must remain live even when Telegram automation is
  // disabled or failover Redis carries a stale disabled config. `enabled` gates
  // Telegram side effects only; scanner state/public feed still advances.
  const nowMs = Date.now();
  const wall = brokerWallParts(nowMs);
  const recoverySeedHour = wall.weekday !== 0 && wall.weekday !== 6 && wall.hour === 5;
  if (wall.weekday === 0 || wall.weekday === 6 || wall.hour < H1_FIRST_SCAN_HOUR || wall.hour > H1_SIGNAL_END_HOUR) {
    return NextResponse.json({
      ok: true,
      enabled,
      dryRun,
      skipped: wall.weekday === 0 || wall.weekday === 6
        ? "broker-weekend"
        : wall.hour < H1_FIRST_SCAN_HOUR
          ? "before-first-slot"
          : "after-last-signal",
      brokerDate: wall.dateKey,
      brokerHour: wall.hour,
      brokerUtcOffsetHours: wall.utcOffsetHours,
    }, { headers: { "Cache-Control": "no-store" } });
  }

  const lockToken = await acquireH1CloudLock();
  if (!lockToken) {
    return NextResponse.json({ ok: true, enabled, dryRun, skipped: "already-running" }, { headers: { "Cache-Control": "no-store" } });
  }

  try {
    const session = await loadH1CTraderSession();
    const market = await fetchReadyMarket(session, nowMs, wall.hour);
    if (!marketReadyForSlot(market, wall.hour)) {
      return NextResponse.json({
        ok: true,
        enabled,
        dryRun,
        skipped: "awaiting-closed-h1",
        brokerDate: market.brokerDate,
        brokerHour: market.brokerHour,
        brokerMinute: market.brokerMinute,
        brokerUtcOffsetHours: market.brokerUtcOffsetHours,
      }, { headers: { "Cache-Control": "no-store, max-age=0" } });
    }
    const { state, source } = await loadH1CloudState(market.brokerDate, market.brokerHour);
    const hadCurrentDay = Boolean(state.days[market.brokerDate]);
    let recoveryDaySeeded = false;
    if (recoverySeedHour && !state.days[market.brokerDate]) {
      state.days[market.brokerDate] = { suppressedThroughHour: market.brokerHour, symbols: {} };
      recoveryDaySeeded = true;
    }
    const recoveredSuppressedHistory = backfillSuppressedHistory(
      state,
      market.brokerDate,
      market.symbols,
    ) > 0;
    let changed = recoveryDaySeeded || recoveredSuppressedHistory;

    // H1 scanner publication is web-only. Telegram block/signal notifications
    // are intentionally disabled; timed BUY/SELL commands are the user-owned
    // source that writes scheduledSignal into the H1 table.
    const pending: RunSummary[] = [];

    // The slot whose candle just closed is slotHour = brokerHour - 1.
    const closedSlotHour = market.brokerHour - 1;
    for (const base of H1_TARGET_BASES) {
      const signals = evaluateH1SignalsForTarget(
        base,
        market.brokerDate,
        market.symbols[base].bars,
        H1_SCAN_HOURS,
        closedSlotHour,
      );
      const { symbol: symbolState } = ensureSymbolDay(state, market.brokerDate, base);
      const delivered = deliveredSlots(symbolState.alerts);
      const day = state.days[market.brokerDate];
      const suppressedThrough = Number(day?.suppressedThroughHour || 0);
      for (let hour = 3; hour <= suppressedThrough; hour += 1) delivered.add(hour);

      for (const signal of signals) {
        const alert: H1StoredAlert = {
          ...signal,
          symbol: market.symbols[base].displayName || base,
        };
        pending.push({
          base,
          slotHour: alert.slotHour,
          signal: alert.symbolH1Signal || "PENDING",
          postSignalRule: alert.postSignalRule,
        });
        if (dryRun) continue;

        const storedIndex = symbolState.alerts.findIndex((item) => item.slotHour === alert.slotHour);
        const sameStored = storedIndex >= 0 && symbolState.alerts[storedIndex].symbolH1Signal === alert.symbolH1Signal;
        if (storedIndex >= 0 && sameStored) continue;
        if (storedIndex >= 0) {
          symbolState.alerts[storedIndex] = {
            ...alert,
            scheduledSignal: symbolState.alerts[storedIndex].scheduledSignal ?? null,
          };
          changed = true;
        } else {
          if (delivered.has(alert.slotHour)) continue;
          symbolState.alerts.push(alert);
          symbolState.alerts.sort((left, right) => left.slotHour - right.slotHour);
          delivered.add(alert.slotHour);
          changed = true;
        }

        // Persist every classified slot for the public table. Manual timed
        // Telegram commands may already have populated scheduledSignal on a
        // placeholder cell; scanner refreshes preserve that user-owned side.
        await saveH1CloudState(state);
      }
    }

    if (!hadCurrentDay && state.days[market.brokerDate]) changed = true;

    if (!dryRun) {
      if (changed || source === "public-seed") await saveH1CloudState(state);
      await publishH1CloudState(state);
    }

    return NextResponse.json({
      ok: true,
      enabled,
      dryRun,
      stateSource: source,
      brokerDate: market.brokerDate,
      brokerHour: market.brokerHour,
      brokerMinute: market.brokerMinute,
      brokerUtcOffsetHours: market.brokerUtcOffsetHours,
      sent: 0,
      blockReminderSent: false,
      pending,
      h1Counts: Object.fromEntries(Object.entries(market.symbols).map(([base, item]) => [base, item.bars.length])),
    }, { headers: { "Cache-Control": "no-store, max-age=0" } });
  } catch (error) {
    console.error("[H1 CLOUD SCANNER]", error instanceof Error ? error.message : String(error));
    return NextResponse.json({ ok: false, error: "H1 cloud scanner run failed." }, {
      status: 502,
      headers: { "Cache-Control": "no-store, max-age=0" },
    });
  } finally {
    await releaseH1CloudLock(lockToken);
  }
}
