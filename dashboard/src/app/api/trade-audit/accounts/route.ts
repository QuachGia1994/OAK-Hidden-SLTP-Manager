import { NextResponse } from "next/server";
import { redis, KEYS, requireAuth, canSeeVipData, isPublicAccountId } from "@/lib/redis";

export const dynamic = "force-dynamic";

type AccountEntry = { public_account_id: string; alias: string };

export async function GET(request: Request) {
  if (!canSeeVipData(request)) return NextResponse.json({ error: "vip_required" }, { status: 403 });
  try {
    const registry = (await redis.get(KEYS.auditAccounts)) as AccountEntry[] | null;
    const list = Array.isArray(registry) ? registry : [];
    // Only return allowlisted public fields.
    const safe = list
      .filter((e) => e && isPublicAccountId(e.public_account_id) && typeof e.alias === "string")
      .map((e) => ({
        public_account_id: e.public_account_id.toLowerCase(),
        alias: e.alias.slice(0, 120),
      }));
    return NextResponse.json({ accounts: safe });
  } catch {
    return NextResponse.json({ accounts: [] });
  }
}

export async function POST(request: Request) {
  const denied = requireAuth(request);
  if (denied) return denied;
  try {
    const body = await request.json();
    const id = String(body?.public_account_id || "").toLowerCase();
    const alias = String(body?.alias || "Account").slice(0, 120);
    if (!isPublicAccountId(id)) {
      return NextResponse.json({ ok: false, error: "invalid_account" }, { status: 400 });
    }
    const registry = ((await redis.get(KEYS.auditAccounts)) as AccountEntry[] | null) || [];
    const list = Array.isArray(registry) ? [...registry] : [];
    const idx = list.findIndex((e) => e?.public_account_id?.toLowerCase() === id);
    const entry = { public_account_id: id, alias };
    if (idx >= 0) list[idx] = entry;
    else list.push(entry);
    await redis.set(KEYS.auditAccounts, list);
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}
