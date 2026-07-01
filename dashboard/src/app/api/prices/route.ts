import { NextResponse } from "next/server";
import { redis, KEYS } from "@/lib/redis";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const prices = await redis.get(KEYS.prices);
    return NextResponse.json(prices || {});
  } catch {
    return NextResponse.json({});
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    await redis.set(KEYS.prices, body);
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
