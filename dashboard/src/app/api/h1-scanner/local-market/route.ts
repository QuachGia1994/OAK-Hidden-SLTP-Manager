import { timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { requireAuth } from "@/lib/redis-core";
import { loadH1CloudConfig } from "@/lib/h1-cloud-config";
import { isValidBrokerDateKey } from "@/lib/h1-broker-date";
import {
  H1_LOCAL_SCAN_HOURS,
  H1_LOCAL_SOURCES,
  H1_LOCAL_TARGETS,
  targetEnabledForDate,
  type H1LocalSource,
  type H1M15Bar,
} from "@/lib/h1-local-patterns";
import {
  acquireH1CloudLock,
  loadH1CloudState,
  publishH1CloudState,
  releaseH1CloudLock,
  saveH1CloudState,
} from "@/lib/h1-cloud-store";
import {
  H1_CLOUD_PROFILE,
  ensureSymbolDay,
  evaluateLocalH1PatternsForTarget,
  type H1LocalMarketSnapshot,
  type H1StoredAlert,
} from "@/lib/h1-cloud-scanner";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const MAX_SNAPSHOT_AGE_MS = 2 * 60 * 1000;
const MAX_BARS_PER_SOURCE = 220;

function safeEqual(left: string, right: string): boolean {
  const a = Buffer.from(left);
  const b = Buffer.from(right);
  return a.length === b.length && timingSafeEqual(a, b);
}

function bearerToken(request: Request): string {
  const header = request.headers.get("authorization") || "";
  return header.startsWith("Bearer ") ? header.slice(7).trim() : "";
}

async function authorize(request: Request): Promise<NextResponse | null> {
  const apiKey = process.env.DASHBOARD_API_KEY || "";
  const bearer = bearerToken(request);
  if (apiKey && bearer) {
    if (!safeEqual(bearer, apiKey)) return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
    return null;
  }
  if (apiKey && request.headers.get("x-api-key")) return requireAuth(request);
  const presented = request.headers.get("x-telegram-bot-api-secret-token") || "";
  if (presented) {
    const config = await loadH1CloudConfig().catch(() => null);
    const expected = config?.telegramWebhookSecret || "";
    if (expected && safeEqual(presented, expected)) return null;
  }
  return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
}

type LocalMarketBody = {
  version?: unknown;
  profile?: unknown;
  capturedAt?: unknown;
  login?: unknown;
  server?: unknown;
  brokerDate?: unknown;
  brokerHour?: unknown;
  brokerMinute?: unknown;
  symbols?: unknown;
};

function parseBar(value: unknown): H1M15Bar | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  const brokerDate = String(row.brokerDate || "");
  const hour = Number(row.hour);
  const minute = Number(row.minute);
  const direction = String(row.direction || "");
  const open = Number(row.open);
  const high = Number(row.high);
  const low = Number(row.low);
  const close = Number(row.close);
  if (!isValidBrokerDateKey(brokerDate)) return null;
  if (!Number.isInteger(hour) || hour < 0 || hour > 23) return null;
  if (![0, 15, 30, 45].includes(minute)) return null;
  if (direction !== "T" && direction !== "G") return null;
  if (![open, high, low, close].every(Number.isFinite)) return null;
  if (high < Math.max(open, close) || low > Math.min(open, close) || high < low) return null;
  if (direction !== (close > open ? "T" : "G")) return null;
  return { brokerDate, hour, minute, direction, open, high, low, close };
}

function parseMarket(body: LocalMarketBody): { brokerDate: string; brokerHour: number; brokerMinute: number; login: number; server: string; market: H1LocalMarketSnapshot } {
  if (Number(body.version) !== 1 || String(body.profile || "") !== H1_CLOUD_PROFILE) throw new Error("invalid local H1 snapshot version/profile");
  const capturedAt = Number(body.capturedAt);
  if (!Number.isFinite(capturedAt) || Math.abs(Date.now() - capturedAt) > MAX_SNAPSHOT_AGE_MS) throw new Error("stale local H1 snapshot");
  const login = Number(body.login);
  const server = String(body.server || "");
  if (!Number.isInteger(login) || login <= 0 || !/icmarkets/i.test(server)) throw new Error("local H1 snapshot must come from ICMarkets MT5");
  const brokerDate = String(body.brokerDate || "");
  const brokerHour = Number(body.brokerHour);
  const brokerMinute = Number(body.brokerMinute);
  if (!isValidBrokerDateKey(brokerDate) || !Number.isInteger(brokerHour) || brokerHour < 0 || brokerHour > 23 || ![0, 15, 30, 45].includes(brokerMinute)) {
    throw new Error("invalid ICMarkets broker wall time");
  }
  if (!body.symbols || typeof body.symbols !== "object") throw new Error("local H1 snapshot symbols missing");
  const sourceRows = body.symbols as Record<string, unknown>;
  const market = {} as H1LocalMarketSnapshot;
  for (const source of H1_LOCAL_SOURCES) {
    const raw = sourceRows[source];
    if (!raw || typeof raw !== "object") throw new Error(`missing local H1 source ${source}`);
    const item = raw as { displayName?: unknown; bars?: unknown };
    if (!Array.isArray(item.bars) || item.bars.length > MAX_BARS_PER_SOURCE) throw new Error(`invalid local H1 bars ${source}`);
    const bars = item.bars.map(parseBar);
    if (bars.some((bar) => !bar)) throw new Error(`invalid local H1 bar ${source}`);
    market[source as H1LocalSource] = { displayName: String(item.displayName || source), bars: bars as H1M15Bar[] };
  }
  return { brokerDate, brokerHour, brokerMinute, login, server, market };
}

function sameAlert(left: H1StoredAlert, right: H1StoredAlert): boolean {
  return left.slotHour === right.slotHour
    && left.entryHour === right.entryHour
    && left.patternGroup === right.patternGroup
    && left.patternFamily === right.patternFamily
    && left.pattern === right.pattern
    && left.scannerSource === right.scannerSource
    && left.baseSymbol === right.baseSymbol
    && left.baseHour === right.baseHour
    && left.baseDirection === right.baseDirection
    && left.baseH1Signal === right.baseH1Signal
    && left.symbolH1Signal === right.symbolH1Signal
    && Boolean(left.inversionBadge) === Boolean(right.inversionBadge)
    && JSON.stringify(left.sampleBars ?? []) === JSON.stringify(right.sampleBars ?? []);
}

export async function POST(request: Request) {
  const denied = await authorize(request);
  if (denied) return denied;
  const body = await request.json().catch(() => null) as LocalMarketBody | null;
  if (!body) return NextResponse.json({ ok: false, error: "invalid json" }, { status: 400 });

  let parsed: ReturnType<typeof parseMarket>;
  try {
    parsed = parseMarket(body);
  } catch (error) {
    return NextResponse.json({ ok: false, error: error instanceof Error ? error.message : "invalid local H1 snapshot" }, { status: 400 });
  }

  const lockToken = await acquireH1CloudLock();
  if (!lockToken) return NextResponse.json({ ok: true, skipped: "already-running", brokerDate: parsed.brokerDate });
  try {
    const { state, source } = await loadH1CloudState(parsed.brokerDate, parsed.brokerHour);
    const dayWasMissing = !state.days[parsed.brokerDate];
    const readyHours = H1_LOCAL_SCAN_HOURS.filter((hour) => hour <= parsed.brokerHour);
    let changed = false;
    let matched = 0;
    let updated = 0;

    for (const target of H1_LOCAL_TARGETS) {
      const computed = evaluateLocalH1PatternsForTarget(target, parsed.brokerDate, parsed.market, readyHours, parsed.brokerHour);
      matched += computed.length;
      const { symbol } = ensureSymbolDay(state, parsed.brokerDate, target);
      const existing = new Map(symbol.alerts.map((alert) => [alert.slotHour, alert]));
      const next: H1StoredAlert[] = [];

      for (const hour of readyHours) {
        const prior = existing.get(hour);
        const fresh = computed.find((alert) => alert.slotHour === hour);
        if (!targetEnabledForDate(target, parsed.brokerDate, hour)) {
          if (prior?.scheduledSignal) next.push({ ...prior, entryHour: null, patternGroup: null, patternFamily: null, pattern: "", scannerSource: "", inversionBadge: false, sampleBars: [] });
          continue;
        }
        if (fresh) {
          const merged = { ...fresh, scheduledSignal: prior?.scheduledSignal ?? null };
          next.push(merged);
          if (!prior || !sameAlert(prior, merged)) {
            changed = true;
            updated += 1;
          }
        } else if (prior?.scheduledSignal) {
          next.push({ ...prior, entryHour: null, patternGroup: null, patternFamily: null, pattern: "", scannerSource: "", inversionBadge: false, sampleBars: [] });
        } else if (prior?.entryHour) {
          changed = true;
          updated += 1;
        }
      }

      for (const prior of symbol.alerts) {
        if (prior.slotHour > parsed.brokerHour) next.push(prior);
      }
      next.sort((a, b) => a.slotHour - b.slotHour);
      if (next.length !== symbol.alerts.length) changed = true;
      symbol.alerts = next;
    }

    if (changed || source === "public-seed" || dayWasMissing) {
      await saveH1CloudState(state);
      await publishH1CloudState(state);
    }

    return NextResponse.json({
      ok: true,
      source: "local-mt5-icmarkets",
      brokerDate: parsed.brokerDate,
      brokerHour: parsed.brokerHour,
      brokerMinute: parsed.brokerMinute,
      login: parsed.login,
      server: parsed.server,
      matched,
      updated,
      changed,
    }, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    console.error("[H1 LOCAL MT5 SCANNER]", error instanceof Error ? error.message : String(error));
    return NextResponse.json({ ok: false, error: "local H1 scanner failed" }, { status: 503 });
  } finally {
    await releaseH1CloudLock(lockToken);
  }
}
