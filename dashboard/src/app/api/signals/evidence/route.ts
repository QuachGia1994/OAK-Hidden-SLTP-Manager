import { NextResponse } from "next/server";
import { redis, KEYS, canSeeVipData } from "@/lib/redis";
import { ACTIVE_SIGNAL_LOGIC_VERSION, DISPLAYED_SIGNAL_PAIRS } from "@/lib/signal-display";
import { isActiveSignalHour } from "@/lib/constants";
import type { SignalEvidence } from "@/lib/types";

export const dynamic = "force-dynamic";

/** GET /api/signals/evidence?date=YYYY-MM-DD&hour=H&symbol=XAUUSD
 *
 * Returns H1 signal evidence for one symbol in the given date/hour slot.
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

  const hourNum = Number(hour);
  if (!Number.isInteger(hourNum) || !isActiveSignalHour(hourNum)) {
    return NextResponse.json({ error: "invalid hour" }, { status: 400 });
  }

  const parsedDate = new Date(`${date}T00:00:00Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(parsedDate.valueOf())
    || parsedDate.toISOString().slice(0, 10) !== date) {
    return NextResponse.json({ error: "invalid date" }, { status: 400 });
  }

  if (!DISPLAYED_SIGNAL_PAIRS.some((pair) => pair === symbol)) {
    return NextResponse.json({ error: "invalid symbol" }, { status: 400 });
  }

  try {
    // Expected incoming evidence structure from bot POST:
    // { "2026-07-29:14:XAUUSD:v71": SignalEvidence }
    const allEvidence = (await redis.get(KEYS.evidence)) as Record<string, SignalEvidence> | null;
    if (!allEvidence) {
      return NextResponse.json({ error: "no evidence data" }, { status: 404 });
    }

    const key = `${date}:${hour}:${symbol}:v${ACTIVE_SIGNAL_LOGIC_VERSION}`;
    const evidence = allEvidence[key];
    if (!evidence) {
      return NextResponse.json({ error: "evidence not found for this slot and version" }, { status: 404 });
    }

    return NextResponse.json(evidence, {
      headers: { "Cache-Control": "private, no-store" },
    });
  } catch (e) {
    return NextResponse.json({ error: "internal error" }, { status: 500 });
  }
}

/** POST /api/signals/evidence
 *
 * Bot pushes evidence data keyed by date:hour:symbol:logic-version.
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

    // Keep the newest 1,000 records (200 complete slots × five symbols).
    const keys = Object.keys(merged).sort();
    if (keys.length > 1000) {
      for (const oldKey of keys.slice(0, keys.length - 1000)) {
        delete merged[oldKey];
      }
    }

    await redis.set(KEYS.evidence, merged);
    return NextResponse.json({ ok: true, count: Object.keys(merged).length });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
