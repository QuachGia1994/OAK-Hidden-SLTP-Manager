import { NextResponse } from "next/server";
import { redis, KEYS, canSeeVipData } from "@/lib/redis";
import { ACTIVE_SIGNAL_LOGIC_VERSION } from "@/lib/signal-display";
import { isActiveSignalHour } from "@/lib/constants";
import { resolveSignalEvidence } from "@/lib/signal-evidence";
import type { Signal, SignalEvidence } from "@/lib/types";

export const dynamic = "force-dynamic";

const EVIDENCE_KEY = /^(\d{4}-\d{2}-\d{2}):(\d+):XAUUSD:v(\d+)$/;

function isCurrentEvidenceEntry(key: string, value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  const match = EVIDENCE_KEY.exec(key);
  if (!match || Number(match[3]) !== ACTIVE_SIGNAL_LOGIC_VERSION) return false;
  const evidence = value as Record<string, unknown>;
  return Number(evidence.logic_version) === ACTIVE_SIGNAL_LOGIC_VERSION
    && (Number(evidence.evidence_schema_version) === 9 || Number(evidence.evidence_schema_version) === 10)
    && Number(evidence.hour) === Number(match[2])
    && evidence.symbol === "XAUUSD";
}

/** GET /api/signals/evidence?date=YYYY-MM-DD&hour=H&symbol=XAUUSD
 *
 * Returns v87 common XAU entry + independent D/relation evidence for one pair.
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
  const version = searchParams.get("version");

  if (!date || !hour || !symbol) {
    return NextResponse.json({ error: "date, hour, and symbol are required" }, { status: 400 });
  }

  const hourNum = Number(hour);
  if (!Number.isInteger(hourNum) || !isActiveSignalHour(hourNum)) {
    return NextResponse.json({ error: "invalid hour" }, { status: 400 });
  }

  const requestedVersion = version === null ? ACTIVE_SIGNAL_LOGIC_VERSION : Number(version);
  if (requestedVersion !== ACTIVE_SIGNAL_LOGIC_VERSION) {
    return NextResponse.json({ error: "unsupported signal logic version" }, { status: 400 });
  }

  const parsedDate = new Date(`${date}T00:00:00Z`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(parsedDate.valueOf())
    || parsedDate.toISOString().slice(0, 10) !== date) {
    return NextResponse.json({ error: "invalid date" }, { status: 400 });
  }

  if (symbol !== "XAUUSD") {
    return NextResponse.json({ error: "invalid symbol" }, { status: 400 });
  }

  try {
    const [allEvidence, signals] = await Promise.all([
      redis.get(KEYS.evidence) as Promise<Record<string, SignalEvidence> | null>,
      redis.get(KEYS.signals) as Promise<Signal[] | null>,
    ]);
    const evidence = resolveSignalEvidence({
      evidenceStore: allEvidence,
      signals: signals || [],
      date,
      hour: hourNum,
      symbol,
      logicVersion: requestedVersion,
    });
    const evidenceKey = `${date}:${hourNum}:XAUUSD:v${requestedVersion}`;
    if (!evidence || !isCurrentEvidenceEntry(evidenceKey, evidence)) {
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

    const rawIncoming = body as Record<string, SignalEvidence>;
    const incoming = Object.fromEntries(
      Object.entries(rawIncoming).filter(([key, value]) => isCurrentEvidenceEntry(key, value) && key.includes(":XAUUSD:")),
    ) as Record<string, SignalEvidence>;
    if (Object.keys(incoming).length === 0) {
      return NextResponse.json({ ok: false, error: "no current v87 evidence entries" }, { status: 400 });
    }
    const rawExisting = ((await redis.get(KEYS.evidence)) as Record<string, SignalEvidence>) || {};
    const existing = Object.fromEntries(
      Object.entries(rawExisting).filter(([key, value]) => isCurrentEvidenceEntry(key, value)),
    ) as Record<string, SignalEvidence>;

    // Merge: replace existing keys with incoming
    const merged = { ...existing, ...incoming };

    // Keep the newest 1,000 single-source XAU entry records.
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
