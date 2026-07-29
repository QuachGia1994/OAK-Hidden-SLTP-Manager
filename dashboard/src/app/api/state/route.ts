import { NextResponse } from "next/server";
import { redis, KEYS, requireAuth, canSeeVipData } from "@/lib/redis";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const state = (await redis.get(KEYS.state)) as Record<string, unknown> | null;
    if (!state) return NextResponse.json(null);
    if (canSeeVipData(request)) return NextResponse.json(state);
    // Public clients only need the current date and idempotency slots.
    return NextResponse.json({
      date: state.date ?? null,
      sent_today: [],
    });
  } catch {
    return NextResponse.json(null);
  }
}

export async function POST(request: Request) {
  const denied = requireAuth(request);
  if (denied) return denied;
  try {
    const body = await request.json();
    await redis.set(KEYS.state, body);
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
