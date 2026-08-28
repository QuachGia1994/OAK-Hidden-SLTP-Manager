import { createHash, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { redis, requireAuth } from "@/lib/redis-core";
import { loadH1CloudConfig, type H1CloudConfig } from "@/lib/h1-cloud-config";
import { verifyH1ScannerGitHubOidc } from "@/lib/github-oidc";
import { brokerWallParts, fetchCurrentBrokerDayMarket, type CTraderScannerSession } from "@/lib/ctrader-json";
import { loadH1CTraderSession } from "@/lib/h1-ctrader-session";
import { cTraderProviderAccountId, providerProtectionPoints } from "@/lib/provider-account-domain";
import { listProviderAccounts } from "@/lib/provider-accounts";
import { TELEGRAM_CLOUD_EXECUTION_MODE } from "@/lib/telegram-cloud-domain";
import { createCloudIntent } from "@/lib/telegram-cloud-store";
import { acquireH1CloudLock, loadH1CloudState, publishH1CloudState, releaseH1CloudLock, saveH1CloudState } from "@/lib/h1-cloud-store";
import {
  H1_FIRST_SCAN_HOUR,
  H1_SIGNAL_END_HOUR,
  H1_TARGET_BASES,
  backfillSuppressedHistory,
  brokerEntryDueAt,
  buildStoredAlert,
  buildTelegramMessage,
  ensureSymbolDay,
  evaluateH1BlocksForTarget,
  targetsForBlockHour,
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
const H1_AUTO_ENTRY_LOT = 0.03;

type RunSummary = {
  base: string;
  slotHour: number;
  patternKind: string;
  m15Pair: string;
  m15Window: string;
  entryTime: string;
  signal: string;
  postSignalRule: string;
  intentId: number | null;
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

async function sendTelegram(message: string, config: H1CloudConfig): Promise<void> {
  const response = await fetch(`https://api.telegram.org/bot${config.telegramToken}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: config.telegramChatId, text: message }),
    cache: "no-store",
  });
  const payload = await response.json().catch(() => ({})) as { ok?: boolean; description?: string };
  if (!response.ok || payload.ok !== true) {
    throw new Error(payload.description || `Telegram send failed (${response.status})`);
  }
}

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function marketReadyForSlot(
  market: Awaited<ReturnType<typeof fetchCurrentBrokerDayMarket>>,
  brokerHour: number,
  brokerMinute: number,
) {
  const expectedClosedHour = brokerHour - 1;
  const blockReady = targetsForBlockHour(brokerHour).every((base) =>
    market.symbols[base].bars.some((bar) => bar.hour === expectedClosedHour),
  );

  // H+2:00 signals need the candle opened at H-1:45; H+1:25 signals
  // become decidable at H+1:15 and need the candle opened at H+1:00.
  const signalSlotHour = brokerMinute < 15 ? brokerHour - 2 : brokerHour - 1;
  const expectedClosedM15Minute = brokerHour * 60 + (brokerMinute < 15 ? -15 : 0);
  const signalPairReady = targetsForBlockHour(signalSlotHour).every((base) =>
    market.symbols[base].m15Bars.some((bar) => bar.minuteOfDay === expectedClosedM15Minute),
  );
  return blockReady && signalPairReady;
}

async function fetchReadyMarket(session: CTraderScannerSession, nowMs: number, brokerHour: number, brokerMinute: number) {
  let market = await fetchCurrentBrokerDayMarket(session, nowMs);
  for (let attempt = 1; attempt < FINALIZE_RETRY_ATTEMPTS && !marketReadyForSlot(market, brokerHour, brokerMinute); attempt += 1) {
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
  if (!enabled && !dryRun) {
    return NextResponse.json({ ok: true, enabled: false, skipped: "disabled" }, { headers: { "Cache-Control": "no-store" } });
  }

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
    const market = await fetchReadyMarket(session, nowMs, wall.hour, wall.minute);
    if (!marketReadyForSlot(market, wall.hour, wall.minute)) {
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
    let recoveryDaySeeded = false;
    if (recoverySeedHour && !state.days[market.brokerDate]) {
      state.days[market.brokerDate] = { suppressedThroughHour: market.brokerHour, symbols: {} };
      recoveryDaySeeded = true;
    }
    const availableThroughMinute = market.brokerHour * 60 + market.brokerMinute;
    const recoveredSuppressedHistory = backfillSuppressedHistory(
      state,
      market.brokerDate,
      market.symbols,
      availableThroughMinute,
    ) > 0;
    let changed = recoveryDaySeeded || recoveredSuppressedHistory;

    const providerTarget = dryRun
      ? null
      : (await listProviderAccounts()).find((account) => account.id === cTraderProviderAccountId(session.accountId) && account.enabled && account.provider === "ctrader") || null;
    const automationReady = !dryRun && Boolean(cloudConfig?.telegramControlEnabled && providerTarget);
    const automationSkippedReason = dryRun
      ? "dry-run"
      : !cloudConfig?.telegramControlEnabled
        ? "telegram-control-disabled"
        : !providerTarget
          ? "enabled-scanner-account-missing"
          : null;

    const pending: RunSummary[] = [];
    let sent = 0;

    for (const base of H1_TARGET_BASES) {
      const evaluations = evaluateH1BlocksForTarget(
        base,
        market.symbols[base].bars,
        market.symbols[base].m15Bars,
        market.brokerHour,
        availableThroughMinute,
      );
      const { symbol: symbolState } = ensureSymbolDay(state, market.brokerDate, base);
      const delivered = deliveredSlots(symbolState.alerts);
      const day = state.days[market.brokerDate];
      const suppressedThrough = Number(day?.suppressedThroughHour || 0);
      for (let hour = 3; hour <= suppressedThrough; hour += 1) delivered.add(hour);

      for (const evaluation of evaluations) {
        if (delivered.has(evaluation.slotHour)) continue;
        const alert = buildStoredAlert({
          base,
          brokerSymbol: market.symbols[base].displayName || base,
          evaluation,
        });
        let intentId: number | null = null;
        let telegramMessage = buildTelegramMessage(base, market.brokerDate, alert);
        if (automationReady) {
          if (!cloudConfig || !providerTarget) throw new Error("H1 automation readiness invariant failed");
          const protection = providerProtectionPoints(providerTarget, alert.symbol);
          const dueAt = brokerEntryDueAt(market.brokerDate, alert.entryTime, market.brokerUtcOffsetHours);
          const task = await createCloudIntent({
            kind: "entry",
            source: "H1 Scanner",
            automationKey: `h1:${market.brokerDate}:${base}:H${alert.slotHour}`,
            chatId: cloudConfig.telegramChatId,
            rawText: `H1 ${base} H${alert.slotHour} ${alert.symbolH1Signal} ${alert.entryTime}`,
            dueAt,
            dueText: `${market.brokerDate} ${alert.entryTime}:00 broker UTC${market.brokerUtcOffsetHours >= 0 ? "+" : ""}${market.brokerUtcOffsetHours}`,
            payload: {
              side: alert.symbolH1Signal,
              symbol: alert.symbol,
              lot: H1_AUTO_ENTRY_LOT,
              sl: 0,
              tp: 0,
              legacyProfile: providerTarget.label,
              executionMode: TELEGRAM_CLOUD_EXECUTION_MODE,
              strategy: "h1-m15-rule-45",
              blockHour: alert.slotHour,
              patternKind: alert.patternKind,
            },
            targetAccountIds: [providerTarget.id],
            protectionPlan: {
              [providerTarget.id]: { label: providerTarget.label, slPoints: protection.sl, tpPoints: protection.tp },
            },
          });
          intentId = task.id;
          telegramMessage = [telegramMessage,
            `• Intent #${task.id}: ${alert.symbolH1Signal} ${alert.symbol} · ${H1_AUTO_ENTRY_LOT} lot · @${providerTarget.label}`,
            `• Trạng thái: ${task.status} · /approve ${task.id}`,
            "• Chưa /approve thì cloud tuyệt đối không execute.",
          ].join("\n");
        }
        pending.push({
          base,
          slotHour: alert.slotHour,
          patternKind: alert.patternKind,
          m15Pair: alert.m15Pair,
          m15Window: alert.m15Window,
          entryTime: alert.entryTime,
          signal: alert.symbolH1Signal,
          postSignalRule: alert.postSignalRule,
          intentId,
        });
        if (dryRun) continue;

        if (automationReady) {
          if (!cloudConfig) throw new Error("H1 automation readiness invariant failed");
          await sendTelegram(telegramMessage, cloudConfig);
          sent += 1;
        }
        symbolState.alerts.push(alert);
        symbolState.alerts.sort((left, right) => left.slotHour - right.slotHour);
        delivered.add(alert.slotHour);
        changed = true;
        // Persist every classified slot for the public table. When automation
        // is ready this still happens only after Telegram succeeds, preserving
        // retry ordering without making analytics depend on trading readiness.
        await saveH1CloudState(state);
      }
    }

    if (!dryRun) {
      if (changed || source === "public-seed") await saveH1CloudState(state);
      await publishH1CloudState(state);
    }

    return NextResponse.json({
      ok: true,
      enabled,
      dryRun,
      automationReady,
      automationSkippedReason,
      stateSource: source,
      brokerDate: market.brokerDate,
      brokerHour: market.brokerHour,
      brokerMinute: market.brokerMinute,
      brokerUtcOffsetHours: market.brokerUtcOffsetHours,
      sent,
      pending,
      h1Counts: Object.fromEntries(Object.entries(market.symbols).map(([base, item]) => [base, item.bars.length])),
      m15Counts: Object.fromEntries(Object.entries(market.symbols).map(([base, item]) => [base, item.m15Bars.length])),
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
