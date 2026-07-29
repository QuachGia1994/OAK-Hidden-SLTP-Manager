import { NextResponse } from "next/server";
import { redis, KEYS, canSeeVipData } from "@/lib/redis";
import { ACTIVE_SIGNAL_LOGIC_VERSION, DISPLAYED_SIGNAL_PAIRS } from "@/lib/signal-display";
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

  if (!date || !hour || !symbol) {
    return NextResponse.json({ error: "date, hour, and symbol are required" }, { status: 400 });
  }

  const hourNum = parseInt(hour, 10);
  if (![3, 7, 9, 12, 14, 16].includes(hourNum)) {
    return NextResponse.json({ error: "invalid hour" }, { status: 400 });
  }

  if (!DISPLAYED_SIGNAL_PAIRS.includes(symbol as any)) {
    return NextResponse.json({ error: "invalid symbol" }, { status: 400 });
  }

  try {
    // Expected incoming evidence structure from bot POST:
    // { "2026-07-29:14:v69": { "XAUUSD": SignalEvidence, "GBPUSD": SignalEvidence, ... } }
    const allEvidence = (await redis.get(KEYS.evidence)) as Record<string, Record<string, SignalEvidence>> | null;
    if (!allEvidence) {
      return NextResponse.json({ error: "no evidence data" }, { status: 404 });
    }

    const key = `${date}:${hour}:v${ACTIVE_SIGNAL_LOGIC_VERSION}`;
    const slotEvidence = allEvidence[key];
    if (!slotEvidence) {
      return NextResponse.json({ error: "evidence not found for this slot and version" }, { status: 404 });
    }

    const pairEvidence = slotEvidence[symbol];
    if (!pairEvidence) {
      return NextResponse.json({ error: "symbol evidence not found" }, { status: 404 });
    }

    return NextResponse.json(pairEvidence, {
      headers: { "Cache-Control": "private, no-store" },
    });
  } catch (e) {
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

    const incoming = body as Record<string, Record<string, SignalEvidence>>;
    const existing = ((await redis.get(KEYS.evidence)) as Record<string, Record<string, SignalEvidence>>) || {};

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
