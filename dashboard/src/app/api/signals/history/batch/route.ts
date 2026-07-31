import { NextResponse } from "next/server";
import { redis, KEYS, requireAuth } from "@/lib/redis";
import { filterDisplayableSignals } from "@/lib/constants";
import type { Signal } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  const denied = requireAuth(request);
  if (denied) return denied;

  try {
    const body: unknown = await request.json();
    let recordsRaw: Array<Signal & Record<string, unknown>> = [];
    let clearAll = false;

    if (body && typeof body === "object" && !Array.isArray(body)) {
      const obj = body as Record<string, unknown>;
      recordsRaw = (Array.isArray(obj.records) ? obj.records : []) as Array<Signal & Record<string, unknown>>;
      clearAll = Boolean(obj.clear_all);
    } else {
      return NextResponse.json({ ok: false, error: "invalid payload format" }, { status: 400 });
    }

    const incoming = filterDisplayableSignals(recordsRaw);
    
    // If clearAll is set, we start fresh (e.g., first chunk of a total rebuild)
    const existing = clearAll ? [] : filterDisplayableSignals(
      ((await redis.get(KEYS.signals)) as Array<Signal & Record<string, unknown>>) || [],
    );

    const map = new Map<string, Signal & Record<string, unknown>>();

    for (const s of existing) {
      map.set(`${s.date}:${s.hour}`, s);
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
    return NextResponse.json({ ok: true, count: merged.length });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
