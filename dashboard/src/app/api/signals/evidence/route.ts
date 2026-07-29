import { NextResponse } from "next/server";
import { redis, KEYS, canSeeVipData } from "@/lib/redis";
import type { SignalEvidence } from "@/lib/types";

export const dynamic = "force-dynamic";

/** GET /api/signals/evidence?date=YYYY-MM-DD&hour=H
 *
 * Returns M15 candle evidence for the given date/hour.
 * VIP-only: non-VIP requests receive 403.
 * Response headers include Cache-Control: private, no-store.
 */
export async function GET(request: Request) {
  if (!canSeeVipData(request)) {
    return NextResponse.json({ error: "vip required" }, { status: 403 });
  }

  const { searchParams } = new URL(request.url);
  const date = searchParams.get("date");
  const hour = searchParams.get("hour");
  const symbol = searchParams.get("symbol");

  if (!date || !hour) {
    return NextResponse.json({ error: "date and hour are required" }, { status: 400 });
  }

  const hourNum = parseInt(hour, 10);
  if (![3, 7, 9, 12, 14, 16].includes(hourNum)) {
    return NextResponse.json({ error: "invalid hour" }, { status: 400 });
  }

  try {
    const allEvidence = (await redis.get(KEYS.evidence)) as Record<string, SignalEvidence> | null;
    if (!allEvidence) {
      return NextResponse.json({ error: "no evidence data" }, { status: 404 });
    }

    const key = `${date}:${hour}`;
    const slotEvidence = allEvidence[key];
    if (!slotEvidence) {
      return NextResponse.json({ error: "evidence not found" }, { status: 404 });
    }

    // If symbol is specified, return only that symbol's evidence
    if (symbol) {
      const pairEvidence = slotEvidence[symbol];
      if (!pairEvidence) {
        return NextResponse.json({ error: "symbol not found" }, { status: 404 });
      }
      return NextResponse.json(pairEvidence, {
        headers: { "Cache-Control": "private, no-store" },
      });
    }

    return NextResponse.json(slotEvidence, {
      headers: { "Cache-Control": "private, no-store" },
    });
  } catch {
    return NextResponse.json({ error: "internal error" }, { status: 500 });
  }
}

/** POST /api/signals/evidence
 *
 * Bot pushes evidence data. Keyed by date:hour → symbol evidence map.
 * Requires API key auth.
 */
export async function POST(request: Request) {
  const { requireAuth } = await import("@/lib/redis");
  const denied = requireAuth(request);
  if (denied) return denied;

  try {
    const body: unknown = await request.json();
    if (!body || typeof body !== "object") {
      return NextResponse.json({ ok: false, error: "body must be an object" }, { status: 400 });
    }

    const incoming = body as Record<string, SignalEvidence>;
    const existing = ((await redis.get(KEYS.evidence)) as Record<string, SignalEvidence>) || {};

    // Merge: replace existing keys with incoming
    const merged = { ...existing, ...incoming };

    // Keep only the last 200 slots of evidence (each slot = date:hour)
    const keys = Object.keys(merged).sort();
    if (keys.length > 200) {
      for (const oldKey of keys.slice(0, keys.length - 200)) {
        delete merged[oldKey];
      }
    }

    await redis.set(KEYS.evidence, merged);
    return NextResponse.json({ ok: true, count: Object.keys(merged).length });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
