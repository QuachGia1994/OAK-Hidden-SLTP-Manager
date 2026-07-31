import { NextResponse } from "next/server";
import { redis, KEYS, requireAuth } from "@/lib/redis";
import type { DDirectionSnapshotV2 } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const date = searchParams.get("date");
  const from = searchParams.get("from");
  const to = searchParams.get("to");

  try {
    if (from && to) {
      const historyMap = (await redis.hgetall(KEYS.dDirectionHistory)) as Record<string, unknown> | null;
      const result: Record<string, unknown> = {};
      if (historyMap) {
        for (const [key, raw] of Object.entries(historyMap)) {
          if (key >= from && key <= to) {
            try {
              result[key] = typeof raw === "string" ? JSON.parse(raw) : raw;
            } catch {
              result[key] = raw;
            }
          }
        }
      }
      return NextResponse.json(result, {
        headers: { "Cache-Control": "private, no-store" },
      });
    }

    if (date) {
      const raw = await redis.hget(KEYS.dDirectionHistory, date);
      if (raw) {
        const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
        return NextResponse.json(parsed, {
          headers: { "Cache-Control": "private, no-store" },
        });
      }
      return NextResponse.json(
        { error: "D_HISTORY_NOT_FOUND", date },
        { status: 404, headers: { "Cache-Control": "private, no-store" } }
      );
    }

    const current = (await redis.get(KEYS.dDirectionCurrent)) as DDirectionSnapshotV2 | null;
    if (current) {
      return NextResponse.json(current, {
        headers: { "Cache-Control": "private, no-store" },
      });
    }

    return NextResponse.json(
      {
        schema_version: 2,
        logic_version: 82,
        target_local_date: date || new Date().toISOString().slice(0, 10),
        target_broker_date: date || new Date().toISOString().slice(0, 10),
        published_at_utc: "",
        published_at_local: "",
        publication_timezone: "Asia/Ho_Chi_Minh",
        publication_rule: "DAILY_AT_06_00_LOCAL",
        broker_utc_offset: null,
        state: "PENDING_PUBLICATION",
        symbols: {},
        message: "Scheduled for 06:00 GMT+7",
      },
      { headers: { "Cache-Control": "private, no-store" } }
    );
  } catch (error) {
    return NextResponse.json(
      { error: String(error) },
      { status: 500, headers: { "Cache-Control": "private, no-store" } }
    );
  }
}

export async function POST(request: Request) {
  const denied = requireAuth(request);
  if (denied) return denied;

  try {
    const body = await request.json();
    if (!body || typeof body !== "object") {
      return NextResponse.json({ ok: false, error: "Invalid payload" }, { status: 400 });
    }

    const targetDate = body.target_local_date;
    const symbols = body.symbols;
    if (!targetDate || !symbols || typeof symbols !== "object") {
      return NextResponse.json({ ok: false, error: "Missing target_local_date or symbols" }, { status: 400 });
    }

    const payload = JSON.stringify(body);
    await redis.set(KEYS.dDirectionCurrent, payload);
    await redis.hset(KEYS.dDirectionHistory, { [targetDate]: payload });

    // Compute a short digest so the bot can verify the exact snapshot was stored
    const digestInput = `${targetDate}:${body.state ?? ""}:${body.logic_version ?? ""}`;
    let digest = "";
    try {
      const encoder = new TextEncoder();
      const data = encoder.encode(payload);
      const hashBuffer = await crypto.subtle.digest("SHA-256", data);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      digest = hashArray.map((b) => b.toString(16).padStart(2, "0")).join("").slice(0, 16);
    } catch {
      digest = digestInput.slice(0, 16);
    }

    return NextResponse.json({
      ok: true,
      target_local_date: targetDate,
      snapshot_state: body.state ?? null,
      logic_version: body.logic_version ?? null,
      schema_version: body.schema_version ?? null,
      digest,
    });
  } catch (error) {
    return NextResponse.json({ ok: false, error: String(error) }, { status: 500 });
  }
}
