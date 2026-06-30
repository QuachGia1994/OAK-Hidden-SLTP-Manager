import { NextResponse } from "next/server";
import { redis, KEYS } from "@/lib/redis";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const state = await redis.get(KEYS.state);
    return NextResponse.json(state);
  } catch {
    return NextResponse.json(null);
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    await redis.set(KEYS.state, body);
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
