import { NextResponse } from "next/server";
import { canSeeVipData, KEYS, redis, requireAuth } from "@/lib/redis";
import { maskStockAdvisory } from "@/lib/data";
import type { StockAdvisory } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const advisory = (await redis.get(KEYS.stockAdvisor)) as StockAdvisory | null;
  if (!advisory) return NextResponse.json(null);
  return NextResponse.json(canSeeVipData(request) ? advisory : maskStockAdvisory(advisory));
}

export async function POST(request: Request) {
  const denied = requireAuth(request);
  if (denied) return denied;
  if (Number(request.headers.get("content-length") || 0) > 65_536) {
    return NextResponse.json({ ok: false, error: "payload too large" }, { status: 413 });
  }
  let advisory: StockAdvisory;
  try {
    const body = await request.text();
    if (new TextEncoder().encode(body).byteLength > 65_536) {
      return NextResponse.json({ ok: false, error: "payload too large" }, { status: 413 });
    }
    advisory = JSON.parse(body) as StockAdvisory;
  } catch {
    return NextResponse.json({ ok: false, error: "invalid JSON payload" }, { status: 400 });
  }
  if (!isSafeAdvisory(advisory)) {
    return NextResponse.json({ ok: false, error: "unsafe advisory payload" }, { status: 400 });
  }
  try {
    await redis.set(KEYS.stockAdvisor, advisory);
    return NextResponse.json({ ok: true, status: advisory.status, candidates: advisory.candidates.length });
  } catch {
    return NextResponse.json({ ok: false, error: "storage unavailable" }, { status: 503 });
  }
}

function isSafeAdvisory(value: StockAdvisory): boolean {
  if (!value || typeof value !== "object") return false;
  if (value.advisory_only !== true || value.requires_user_confirmation !== true) return false;
  if (value.orders_submitted !== false || !Array.isArray(value.candidates)) return false;
  if (value.action !== "BUY_OR_HOLD" && value.action !== "SELL_OR_AVOID") return false;
  return value.candidates.length <= 50;
}
