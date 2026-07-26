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

export async function POST(request: Request) {
  const denied = requireAuth(request);
  if (denied) return denied;
  try {
    const body: unknown = await request.json();
    if (!Array.isArray(body)) {
      return NextResponse.json({ ok: false, error: "body must be an array" }, { status: 400 });
    }
    const incoming = filterDisplayableSignals(body as Array<Signal & Record<string, unknown>>).slice(-2000);

    // A bot push contains the rebuilt history for its dates. Replace those
    // dates atomically so removed slots do
    // not survive indefinitely in Redis.
    const existing = filterDisplayableSignals(
      ((await redis.get(KEYS.signals)) as Array<Signal & Record<string, unknown>>) || [],
    );
    const incomingDates = new Set(incoming.map((signal) => signal?.date).filter(Boolean));
    const map = new Map<string, Signal & Record<string, unknown>>();
    for (const s of existing) {
      if (!incomingDates.has(s?.date)) map.set(`${s.date}:${s.hour}`, s);
    }
    for (const s of incoming) map.set(`${s.date}:${s.hour}`, s);
    const merged = [...map.values()].sort((a, b) => b.ts - a.ts).slice(0, 2000);
    await redis.set(KEYS.signals, merged);
    return NextResponse.json({ ok: true, count: merged.length });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
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
