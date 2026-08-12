import { NextResponse } from "next/server";
import { redis, KEYS, requireAuth, canSeeVipData } from "@/lib/redis";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  if (!canSeeVipData(request)) return NextResponse.json({ error: "vip_required" }, { status: 403 });
  try {
    const payload = await redis.get(KEYS.auditOverview);
    return NextResponse.json(payload ?? null);
  } catch {
    return NextResponse.json(null);
  }
}

export async function POST(request: Request) {
  const denied = requireAuth(request);
  if (denied) return denied;
  try {
    const body = await request.json();
    await redis.set(KEYS.auditOverview, body);
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
