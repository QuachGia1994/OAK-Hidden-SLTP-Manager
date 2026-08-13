import { NextResponse } from "next/server";
import { redis, KEYS, requireAuth, canSeeVipData, isPublicAccountId, auditKey } from "@/lib/redis";

export function accountFromRequest(request: Request): string | null {
  const url = new URL(request.url);
  const raw = url.searchParams.get("account") || "";
  if (!raw) return null;
  if (!isPublicAccountId(raw)) return null;
  return raw.toLowerCase();
}

export async function getAuditSection(
  request: Request,
  baseKey: string,
): Promise<NextResponse> {
  if (!canSeeVipData(request)) {
    return NextResponse.json({ error: "vip_required" }, { status: 403 });
  }
  const account = accountFromRequest(request);
  // Invalid account param → 404 (do not leak internal existence).
  const url = new URL(request.url);
  if (url.searchParams.has("account") && !account) {
    return NextResponse.json({ error: "not_found" }, { status: 404 });
  }
  try {
    const key = auditKey(baseKey, account);
    const payload = await redis.get(key);
    if (payload == null && account) {
      return NextResponse.json({ error: "not_found" }, { status: 404 });
    }
    return NextResponse.json(payload ?? null);
  } catch {
    return NextResponse.json(null);
  }
}

export async function postAuditSection(
  request: Request,
  baseKey: string,
): Promise<NextResponse> {
  const denied = requireAuth(request);
  if (denied) return denied;
  const account = accountFromRequest(request);
  const url = new URL(request.url);
  if (url.searchParams.has("account") && !account) {
    return NextResponse.json({ error: "invalid_account" }, { status: 400 });
  }
  try {
    const body = await request.json();
    const key = auditKey(baseKey, account);
    await redis.set(key, body);
    // Keep legacy single-slot key warm only when no account namespace (compat).
    if (!account) {
      await redis.set(baseKey, body);
    }
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json({ ok: false, error: String(e) }, { status: 500 });
  }
}

export { KEYS };
