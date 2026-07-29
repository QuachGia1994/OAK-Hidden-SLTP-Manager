import { NextResponse } from "next/server";
import { redis, KEYS, requireAuth, canSeeVipData, maskSignalForPublic } from "@/lib/redis";
import { filterDisplayableSignals } from "@/lib/constants";
import type { Signal } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const signals = filterDisplayableSignals(
      ((await redis.get(KEYS.signals)) as Array<Signal & Record<string, unknown>>) || [],
    );
    if (canSeeVipData(request)) {
      return NextResponse.json(signals);
    }
    // Public scrape path: hide BUY/SELL and pair dirs (VIP SSR still uses Redis server-side)
    return NextResponse.json(signals.map((s) => maskSignalForPublic(s)));
  } catch {
    return NextResponse.json([]);
  }
}

export async function POST(request: Request) {
  const denied = requireAuth(request);
  if (denied) return denied;
  try {
    const body: unknown = await request.json();
    let mode: "UPSERT" | "FULL_SNAPSHOT" = "UPSERT";
    let snapshotComplete = false;
    let recordsRaw: Array<Signal & Record<string, unknown>> = [];

    if (Array.isArray(body)) {
      recordsRaw = body as Array<Signal & Record<string, unknown>>;
      mode = "UPSERT";
    } else if (body && typeof body === "object") {
      const obj = body as Record<string, unknown>;
      mode = obj.mode === "FULL_SNAPSHOT" ? "FULL_SNAPSHOT" : "UPSERT";
      snapshotComplete = Boolean(obj.snapshot_complete);
      recordsRaw = (Array.isArray(obj.records) ? obj.records : []) as Array<Signal & Record<string, unknown>>;
    } else {
      return NextResponse.json({ ok: false, error: "invalid payload format" }, { status: 400 });
    }

    if (mode === "FULL_SNAPSHOT" && !snapshotComplete) {
      return NextResponse.json(
        { ok: false, error: "FULL_SNAPSHOT mode requires snapshot_complete: true" },
        { status: 400 },
      );
    }

    const incoming = filterDisplayableSignals(recordsRaw).slice(-2000);
    const existing = filterDisplayableSignals(
      ((await redis.get(KEYS.signals)) as Array<Signal & Record<string, unknown>>) || [],
    );

    const map = new Map<string, Signal & Record<string, unknown>>();

    if (mode === "FULL_SNAPSHOT") {
      const incomingDates = new Set(incoming.map((s) => s?.date).filter(Boolean));
      for (const s of existing) {
        if (!incomingDates.has(s?.date)) {
          map.set(`${s.date}:${s.hour}`, s);
        }
      }
    } else {
      // UPSERT: preserve all existing records by default
      for (const s of existing) {
        map.set(`${s.date}:${s.hour}`, s);
      }
    }

    for (const inc of incoming) {
      const key = `${inc.date}:${inc.hour}`;
      const prev = map.get(key);

      if (!prev) {
        map.set(key, inc);
        continue;
      }

      const incVer = Number(inc.logic_version || 0);
      const prevVer = Number(prev.logic_version || 0);

      if (incVer > prevVer) {
        map.set(key, inc);
        continue;
      }

      if (incVer < prevVer) {
        continue;
      }

      const incRev = Number(inc.record_revision || 0);
      const prevRev = Number(prev.record_revision || 0);

      if (incRev > prevRev) {
        map.set(key, inc);
        continue;
      }

      if (incRev < prevRev) {
        continue;
      }

      const incTime = inc.state_updated_at_utc ? new Date(String(inc.state_updated_at_utc)).getTime() : 0;
      const prevTime = prev.state_updated_at_utc ? new Date(String(prev.state_updated_at_utc)).getTime() : 0;

      if (incTime >= prevTime || (inc.ts || 0) >= (prev.ts || 0)) {
        map.set(key, inc);
      }
    }

    const merged = [...map.values()].sort((a, b) => (b.ts || 0) - (a.ts || 0)).slice(0, 2000);
    await redis.set(KEYS.signals, merged);
    return NextResponse.json({ ok: true, count: merged.length, mode });
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
