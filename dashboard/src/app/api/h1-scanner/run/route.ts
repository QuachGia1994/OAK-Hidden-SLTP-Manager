import { randomUUID } from "node:crypto";
import { NextResponse } from "next/server";
import { redis, requireAuth } from "@/lib/redis-core";
import { getFreshCTraderTokens } from "@/lib/ctrader-vault";
import { loadH1CloudConfig, type H1CloudConfig } from "@/lib/h1-cloud-config";
import { verifyH1ScannerGitHubOidc } from "@/lib/github-oidc";
import { brokerWallParts, fetchCurrentBrokerDayH1, type CTraderScannerSession } from "@/lib/ctrader-json";
import {
  H1_CLOUD_LOCK_KEY,
  H1_CLOUD_PROFILE,
  H1_CLOUD_STATE_KEY,
  H1_PUBLIC_LATEST_KEY,
  H1_TARGET_BASES,
  buildPublicFeed,
  buildStoredAlert,
  buildTelegramMessage,
  ensureSymbolDay,
  findH1PatternMatches,
  parseCloudState,
  seedCloudStateFromPublic,
  trimCloudState,
  type H1CloudState,
  type H1StoredAlert,
} from "@/lib/h1-cloud-scanner";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const PUBLIC_PROFILE_KEY = `robot-sltp:public:h1-signals:${H1_CLOUD_PROFILE}`;
const RUN_TICKET_HEADER = "x-h1-run-ticket";
const RUN_TICKET_PREFIX = "oak:h1:run-ticket:";
const LOCK_SECONDS = 90;

type RunSummary = {
  base: string;
  slotHour: number;
  patternKind: string;
  signal: string;
  gbpusdSignal: string;
};

async function authorize(request: Request): Promise<NextResponse | null> {
  // Existing server-to-server API auth remains available for manual/admin runs.
  const apiDenied = requireAuth(request);
  if (!apiDenied) return null;

  // Scheduled runs use GitHub Actions OIDC; no scanner secret is stored in GitHub.
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

async function loadState(): Promise<{ state: H1CloudState; source: "cloud" | "public-seed" }> {
  const existing = await redis.get<unknown>(H1_CLOUD_STATE_KEY);
  if (existing) return { state: parseCloudState(existing), source: "cloud" };
  const publicFeed = await redis.get<unknown>(H1_PUBLIC_LATEST_KEY);
  return { state: seedCloudStateFromPublic(publicFeed), source: "public-seed" };
}

async function saveState(state: H1CloudState): Promise<void> {
  trimCloudState(state, 14);
  await redis.set(H1_CLOUD_STATE_KEY, state);
}

async function publishState(state: H1CloudState): Promise<void> {
  const feed = buildPublicFeed(state);
  await Promise.all([
    redis.set(PUBLIC_PROFILE_KEY, feed),
    redis.set(H1_PUBLIC_LATEST_KEY, feed),
  ]);
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

async function acquireLock(token: string): Promise<boolean> {
  const result = await redis.set(H1_CLOUD_LOCK_KEY, token, { nx: true, ex: LOCK_SECONDS });
  return result === "OK";
}

async function releaseLock(token: string): Promise<void> {
  try {
    const current = await redis.get<string>(H1_CLOUD_LOCK_KEY);
    if (current === token) await redis.del(H1_CLOUD_LOCK_KEY);
  } catch {
    // TTL is the final safety net. Never mask the scanner result on unlock failure.
  }
}

function sessionConfig(token: Awaited<ReturnType<typeof getFreshCTraderTokens>>): CTraderScannerSession {
  if (!token) throw new Error("cTrader account has not been authorised");
  const clientId = process.env.OAK_CTRADER_CLIENT_ID || "";
  const clientSecret = process.env.OAK_CTRADER_CLIENT_SECRET || "";
  const accountId = Number.parseInt(process.env.OAK_CTRADER_ACCOUNT_ID || "", 10) || 0;
  if (!clientId || !clientSecret || accountId <= 0) throw new Error("cTrader application/account configuration is incomplete");
  const environment = (process.env.OAK_CTRADER_ENV || "demo").toLowerCase() === "live" ? "live" : "demo";
  return {
    clientId,
    clientSecret,
    accessToken: token.accessToken,
    accountId,
    environment,
    broker: process.env.OAK_CTRADER_BROKER || "ICMarkets",
    scope: token.scope,
  };
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
  if (wall.weekday === 0 || wall.weekday === 6 || wall.hour < 3) {
    return NextResponse.json({
      ok: true,
      enabled,
      dryRun,
      skipped: wall.weekday === 0 || wall.weekday === 6 ? "broker-weekend" : "before-first-slot",
      brokerDate: wall.dateKey,
      brokerHour: wall.hour,
    }, { headers: { "Cache-Control": "no-store" } });
  }

  const lockToken = randomUUID();
  if (!await acquireLock(lockToken)) {
    return NextResponse.json({ ok: true, enabled, dryRun, skipped: "already-running" }, { headers: { "Cache-Control": "no-store" } });
  }

  try {
    const { state, source } = await loadState();
    const tokens = await getFreshCTraderTokens();
    const market = await fetchCurrentBrokerDayH1(sessionConfig(tokens), nowMs);
    const gbpByHour = new Map(market.symbols.GBPUSD.bars.map((bar) => [bar.hour, bar]));
    const pending: RunSummary[] = [];
    let sent = 0;
    let changed = false;

    for (const base of H1_TARGET_BASES) {
      const firstScanHour = base === "XAUUSD" ? 4 : 3;
      const matches = findH1PatternMatches(market.symbols[base].bars, market.brokerHour, firstScanHour);
      const symbolState = ensureSymbolDay(state, market.brokerDate, base);
      const delivered = deliveredSlots(symbolState.alerts);

      for (const match of matches) {
        if (delivered.has(match.slotHour)) continue;
        const gbpBase = gbpByHour.get(match.slotHour - 1);
        if (!gbpBase) break;
        const alert = buildStoredAlert({
          base,
          brokerSymbol: market.symbols[base].displayName || base,
          match,
          gbpBase,
        });
        pending.push({
          base,
          slotHour: alert.slotHour,
          patternKind: alert.patternKind,
          signal: alert.symbolH1Signal,
          gbpusdSignal: alert.gbpusdH1Signal,
        });
        if (dryRun) continue;

        if (!cloudConfig) throw new Error("H1 cloud scanner config is unavailable");
        await sendTelegram(buildTelegramMessage(base, market.brokerDate, alert), cloudConfig);
        symbolState.alerts.push(alert);
        symbolState.alerts.sort((left, right) => left.slotHour - right.slotHour);
        delivered.add(alert.slotHour);
        sent += 1;
        changed = true;
        // Persist immediately after Telegram success to minimize replay risk if
        // a later symbol/network request fails in the same invocation.
        await saveState(state);
      }
    }

    if (!dryRun) {
      if (!changed && source === "public-seed") await saveState(state);
      await publishState(state);
    }

    return NextResponse.json({
      ok: true,
      enabled,
      dryRun,
      stateSource: source,
      brokerDate: market.brokerDate,
      brokerHour: market.brokerHour,
      brokerMinute: market.brokerMinute,
      sent,
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
    await releaseLock(lockToken);
  }
}
