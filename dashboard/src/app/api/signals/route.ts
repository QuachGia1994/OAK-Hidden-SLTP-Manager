import { NextResponse } from "next/server";
import { redis, KEYS } from "@/lib/redis";

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
  try {
    const body = await request.json();
    // Merge with existing signals, deduplicate by (date, hour)
    const existing = (await redis.get(KEYS.signals)) || [];
    const merged = [...(existing as any[]), ...body];
    const seen = new Map<string, any>();
    for (const s of merged) {
      const key = `${s.date}-${s.hour}`;
      const existing = seen.get(key);
      if (!existing || s.ts > existing.ts) {
        seen.set(key, s);
      }
    }
    // Keep last 500
    const result = Array.from(seen.values()).slice(-500);
    await redis.set(KEYS.signals, result);
    return NextResponse.json({ ok: true, count: result.length });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
