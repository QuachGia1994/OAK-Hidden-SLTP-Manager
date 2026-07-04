import { NextResponse } from "next/server";
import { redis, KEYS, requireAuth } from "@/lib/redis";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const signals = await redis.get(KEYS.signals);
    return NextResponse.json(signals || []);
  } catch {
    return NextResponse.json([]);
  }
}

export async function POST(request: Request) {
  const denied = requireAuth(request);
  if (denied) return denied;
  try {
    const body = await request.json();
    const incoming = (body as any[]).slice(-2000);

    // Merge: keep existing + incoming, dedup by (date, hour)
    const existing = ((await redis.get(KEYS.signals)) as any[]) || [];
    const map = new Map<string, any>();
    for (const s of existing) map.set(`${s.date}:${s.hour}`, s);
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
