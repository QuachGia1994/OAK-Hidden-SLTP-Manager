import { timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { requireAuth } from "@/lib/redis-core";
import { loadH1CloudConfig } from "@/lib/h1-cloud-config";
import { writeTelegramScheduledSignal } from "@/lib/h1-cloud-store";
import type { H1Signal } from "@/lib/h1-cloud-scanner";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// Optional local-primary -> web sync path: the PC controller publishes timed Telegram
// entry signals into the H1 table. This endpoint never touches broker state and must
// never block or fail local execution; the controller defers and retries on errors.
const SIDES = new Set(["BUY", "SELL"]);

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

  // Local-only fallback: reuse the already-provisioned Telegram webhook secret as
  // a server-to-server sync credential. It never reaches browser code.
  const presented = request.headers.get("x-telegram-bot-api-secret-token") || "";
  if (presented) {
    const config = await loadH1CloudConfig().catch(() => null);
    const expected = config?.telegramWebhookSecret || "";
    if (expected && safeEqual(presented, expected)) return null;
  }
  return NextResponse.json({ ok: false, error: "unauthorized" }, { status: 401 });
}

export async function POST(request: Request) {
  const denied = await authorize(request);
  if (denied) return denied;

  const body = await request.json().catch(() => null) as { symbol?: unknown; side?: unknown; dueAt?: unknown } | null;
  const symbol = String(body?.symbol || "").trim().toUpperCase();
  const side = String(body?.side || "").trim().toUpperCase();
  const dueAt = Number(body?.dueAt);
  if (!symbol || symbol.length > 30) return NextResponse.json({ ok: false, error: "invalid symbol" }, { status: 400 });
  if (!SIDES.has(side)) return NextResponse.json({ ok: false, error: "side must be BUY or SELL" }, { status: 400 });
  if (!Number.isFinite(dueAt) || dueAt <= 0) return NextResponse.json({ ok: false, error: "invalid dueAt" }, { status: 400 });

  try {
    // SIDES validation above narrows side to BUY|SELL, the H1Signal domain.
    const result = await writeTelegramScheduledSignal({ symbol, side: side as H1Signal, dueAt });
    if (!result) return NextResponse.json({ ok: true, skipped: "not-mappable" });
    return NextResponse.json({ ok: true, ...result });
  } catch (error) {
    // Lock-busy and transient Redis failures return 503 so the controller defers and retries.
    console.error("[TELEGRAM LOCAL SIGNAL]", error instanceof Error ? error.message : String(error));
    return NextResponse.json({ ok: false, error: "H1 signal sync failed; retry later." }, { status: 503 });
  }
}
