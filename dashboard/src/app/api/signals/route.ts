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
    // Replace entirely instead of merge — bot sends full list each time
    const result = (body as any[]).slice(-500);
    await redis.set(KEYS.signals, result);
    return NextResponse.json({ ok: true, count: result.length });
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
