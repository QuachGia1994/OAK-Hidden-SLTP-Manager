import { NextResponse } from "next/server";
import { redis, requireAuth } from "@/lib/redis";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const profile = searchParams.get("profile") || "default";
    const key = `sltp:heartbeat:${profile}`;
    const hb = await redis.get(key);
    return NextResponse.json(hb);
  } catch {
    return NextResponse.json(null);
  }
}

export async function POST(request: Request) {
  const denied = requireAuth(request);
  if (denied) return denied;
  try {
    const { searchParams } = new URL(request.url);
    const profile = searchParams.get("profile") || "default";
    const key = `sltp:heartbeat:${profile}`;
    const body = await request.json();
    await redis.set(key, body);
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
