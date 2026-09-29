import { timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { requireAuth } from "@/lib/redis-core";
import { loadH1CloudConfig } from "@/lib/h1-cloud-config";
import { isValidBrokerDateKey } from "@/lib/h1-broker-date";
import { H1_FIXED_ENTRY_TIMES } from "@/lib/h1-entry-schedule";
import { H1_CLOUD_PROFILE, H1_SIGNAL_RULE_VERSION } from "@/lib/h1-cloud-scanner";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const MAX_SNAPSHOT_AGE_MS = 2 * 60 * 1000;

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
};

function parseSnapshot(body: LocalMarketBody) {
  if (Number(body.version) !== 2 || String(body.profile || "") !== "MT5 ICMarkets Local") {
    throw new Error("invalid local H1 snapshot version/profile");
  }
  const capturedAt = Number(body.capturedAt);
  if (!Number.isFinite(capturedAt) || Math.abs(Date.now() - capturedAt) > MAX_SNAPSHOT_AGE_MS) {
    throw new Error("stale local H1 snapshot");
  }
  const login = Number(body.login);
  const server = String(body.server || "");
  const brokerDate = String(body.brokerDate || "");
  const brokerHour = Number(body.brokerHour);
  const brokerMinute = Number(body.brokerMinute);
  if (!Number.isInteger(login) || login <= 0 || !/icmarkets/i.test(server)) {
    throw new Error("local H1 snapshot must come from ICMarkets MT5");
  }
  if (!isValidBrokerDateKey(brokerDate)
    || !Number.isInteger(brokerHour) || brokerHour < 0 || brokerHour > 23
    || ![0, 15, 30, 45].includes(brokerMinute)) {
    throw new Error("invalid ICMarkets broker wall time");
  }
  return { login, server, brokerDate, brokerHour, brokerMinute };
}

export async function POST(request: Request) {
  const denied = await authorize(request);
  if (denied) return denied;

  const body = await request.json().catch(() => null) as LocalMarketBody | null;
  if (!body) return NextResponse.json({ ok: false, error: "invalid json" }, { status: 400 });

  try {
    const snapshot = parseSnapshot(body);
    return NextResponse.json({
      ok: true,
      source: H1_CLOUD_PROFILE,
      ...snapshot,
      matched: 0,
      updated: 0,
      changed: false,
      calculationDisabled: true,
      signalRuleVersion: H1_SIGNAL_RULE_VERSION,
      entryTimes: H1_FIXED_ENTRY_TIMES,
      tpMilestones: [],
    }, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    return NextResponse.json({
      ok: false,
      error: error instanceof Error ? error.message : "invalid local H1 snapshot",
    }, { status: 400, headers: { "Cache-Control": "no-store" } });
  }
}
