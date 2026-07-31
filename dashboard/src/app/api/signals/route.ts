import { NextResponse } from "next/server";
import { redis, KEYS, requireAuth, canSeeVipData, maskSignalForPublic } from "@/lib/redis";
import { filterDisplayableSignals } from "@/lib/constants";
import type { Signal } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const signals = filterDisplayableSignals(
      ((await redis.get(KEYS.signals)) as Array<Signal & Record<string, unknown>>) || [],
    );
    if (canSeeVipData(request)) {
      return NextResponse.json(signals);
    }
    // Public scrape path: hide BUY/SELL and pair dirs (VIP SSR still uses Redis server-side)
    return NextResponse.json(signals.map((s) => maskSignalForPublic(s)));
  } catch {
    return NextResponse.json([]);
  }
}

export async function DELETE(request: Request) {
  const denied = requireAuth(request);
  if (denied) return denied;
  try {
    await redis.set(KEYS.signals, []);
    return NextResponse.json({ ok: true, cleared: true });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
