import { NextResponse } from "next/server";
import { redis, KEYS, requireAuth } from "@/lib/redis";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const news = await redis.get(KEYS.news);
    return NextResponse.json(news || []);
  } catch {
    return NextResponse.json([]);
  }
}

export async function POST(request: Request) {
  const denied = requireAuth(request);
  if (denied) return denied;
  try {
    const body = await request.json();
    await redis.set(KEYS.news, body);
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
