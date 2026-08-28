import { timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { redis } from "@/lib/redis-core";
import { createVipCookieValue, getVipAccessState, VIP_COOKIE } from "@/lib/vip";

export const dynamic = "force-dynamic";

function sameSecret(left: string, right: string): boolean {
  const a = Buffer.from(left);
  const b = Buffer.from(right);
  return a.length === b.length && timingSafeEqual(a, b);
}

function clientKey(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for") || "unknown";
  return forwarded.split(",")[0].trim().replace(/[^a-zA-Z0-9:._-]/g, "_");
}

async function allowAttempt(request: Request): Promise<boolean> {
  const bucket = Math.floor(Date.now() / (10 * 60 * 1000));
  const key = `sltp:vip:attempt:${clientKey(request)}:${bucket}`;
  const count = await redis.incr(key);
  if (count === 1) await redis.expire(key, 660);
  return count <= 10;
}

export async function GET(request: Request) {
  const state = getVipAccessState(request.headers.get("cookie") || "");
  return NextResponse.json({ ok: true, ...state });
}

export async function POST(request: Request) {
  const secret = process.env.VIP_TOKEN || "";
  if (!secret) {
    return NextResponse.json({ ok: false, error: "VIP_TOKEN is not configured." }, { status: 503 });
  }

  let allowed = false;
  try {
    allowed = await allowAttempt(request);
  } catch (error) {
    console.error("[VIP SERVICE UNAVAILABLE]", error instanceof Error ? error.message : String(error));
    return NextResponse.json({ ok: false, error: "VIP service is temporarily unavailable. Please try again in a minute." }, { status: 503 });
  }
  if (!allowed) {
    return NextResponse.json({ ok: false, error: "Too many VIP unlock attempts. Try again later." }, { status: 429 });
  }

  const body = await request.json().catch(() => ({}));
  const token = typeof body.token === "string" ? body.token.trim() : "";
  if (!token || !sameSecret(token, secret)) {
    return NextResponse.json({ ok: false, error: "Invalid VIP access code." }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true, unlocked: true });
  response.cookies.set(VIP_COOKIE, createVipCookieValue(secret), {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24 * 30,
  });
  return response;
}

export async function DELETE() {
  const response = NextResponse.json({ ok: true, unlocked: false });
  response.cookies.set(VIP_COOKIE, "", {
    httpOnly: true,
    secure: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  return response;
}
