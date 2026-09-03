import { timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { requireAuth } from "@/lib/redis-core";
import { loadH1CloudConfig } from "@/lib/h1-cloud-config";
import { writeLocalPrimaryFence, type LocalPrimaryMt5Heartbeat } from "@/lib/local-primary-fence";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const MAX_ACCOUNTS = 20;
const MAX_CLOCK_SKEW_MS = 5 * 60_000;

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

function normalizeHeartbeat(value: unknown, now: number): LocalPrimaryMt5Heartbeat | null {
  if (!value || typeof value !== "object") return null;
  const row = value as Record<string, unknown>;
  const providerAccountId = String(row.providerAccountId || "").trim();
  const profile = String(row.profile || "").trim().slice(0, 120);
  const login = Number(row.login);
  const server = String(row.server || "").trim().slice(0, 120);
  const at = Number(row.at);
  const eaVersion = String(row.eaVersion || "").trim().slice(0, 40);
  if (!/^mt5:[A-Za-z0-9_-]{8,80}$/.test(providerAccountId)) return null;
  if (!profile || !Number.isSafeInteger(login) || login <= 0 || !server) return null;
  if (!Number.isFinite(at) || Math.abs(now - at) > MAX_CLOCK_SKEW_MS) return null;
  return { providerAccountId, profile, login, server, at, localReady: row.localReady !== false, eaVersion };
}

export async function POST(request: Request) {
  const denied = await authorize(request);
  if (denied) return denied;

  const body = await request.json().catch(() => null) as { epoch?: unknown; accounts?: unknown } | null;
  if (!body || !Array.isArray(body.accounts) || body.accounts.length > MAX_ACCOUNTS) {
    return NextResponse.json({ ok: false, error: "invalid accounts" }, { status: 400 });
  }

  const now = Date.now();
  const accounts = body.accounts.flatMap((row) => {
    const normalized = normalizeHeartbeat(row, now);
    return normalized ? [normalized] : [];
  });
  if (accounts.length !== body.accounts.length) {
    return NextResponse.json({ ok: false, error: "invalid local heartbeat" }, { status: 400 });
  }

  try {
    await writeLocalPrimaryFence({ at: now, epoch: String(body.epoch || "").slice(0, 120), accounts });
    return NextResponse.json({ ok: true, accounts: accounts.length, at: now }, { headers: { "Cache-Control": "no-store" } });
  } catch (error) {
    console.error("[TELEGRAM LOCAL STATUS]", error instanceof Error ? error.message : String(error));
    return NextResponse.json({ ok: false, error: "Local MT5 status sync failed; retry later." }, { status: 503 });
  }
}
