import { NextResponse } from "next/server";
import { redis, KEYS, requireAuth, canSeeVipData } from "@/lib/redis";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const state = (await redis.get(KEYS.state)) as Record<string, unknown> | null;
    if (!state) return NextResponse.json(null);
    if (canSeeVipData(request)) return NextResponse.json(state);
    // Hide D-direction and day signal payloads from unauthenticated scrapers
    return NextResponse.json({
      date: state.date ?? null,
      d_direction: null,
      d_direction_date: null,
      d_matched_hour: null,
      day_signals: {},
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
