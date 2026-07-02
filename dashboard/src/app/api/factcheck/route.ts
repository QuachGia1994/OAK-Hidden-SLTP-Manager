import { NextResponse } from "next/server";
import { redis, KEYS } from "@/lib/redis";
import type { FactCheckRequest } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const id = searchParams.get("id");
    const status = searchParams.get("status");

    const data = (await redis.get(KEYS.factcheck)) as FactCheckRequest[] | null;
    const items = data || [];

    if (id) {
      const item = items.find((i) => i.id === id);
      return NextResponse.json(item || null);
    }

    if (status) {
      return NextResponse.json(items.filter((i) => i.status === status));
    }

    return NextResponse.json(items.slice(-50));
  } catch {
    return NextResponse.json([]);
  }
}

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const text = body.text?.trim();
    if (!text) {
      return NextResponse.json({ ok: false, error: "text is required" }, { status: 400 });
    }

    const id = crypto.randomUUID();
    const item: FactCheckRequest = {
      id,
      text,
      image_url: body.image_url || undefined,
      status: "pending",
      created_at: Date.now(),
    };

    const data = (await redis.get(KEYS.factcheck)) as FactCheckRequest[] | null;
    const items = data || [];
    items.push(item);
    await redis.set(KEYS.factcheck, items.slice(-200));

    return NextResponse.json({ ok: true, id });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}

export async function PATCH(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const id = searchParams.get("id");
    if (!id) {
      return NextResponse.json({ ok: false, error: "id required" }, { status: 400 });
    }

    const body = await request.json();
    const data = (await redis.get(KEYS.factcheck)) as FactCheckRequest[] | null;
    const items = data || [];
    const idx = items.findIndex((i) => i.id === id);
    if (idx === -1) {
      return NextResponse.json({ ok: false, error: "not found" }, { status: 404 });
    }

    items[idx] = { ...items[idx], ...body };
    await redis.set(KEYS.factcheck, items.slice(-200));

    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
