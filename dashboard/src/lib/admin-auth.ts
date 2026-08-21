import "server-only";

import { createHmac, timingSafeEqual } from "node:crypto";
import { NextResponse } from "next/server";
import { requireAuth } from "@/lib/redis-core";

export const ADMIN_SESSION_COOKIE = "oak_admin_session";
const SESSION_CONTEXT = "oak-admin-session-v2";
const SESSION_TTL_MS = 12 * 60 * 60 * 1000;

function apiKey(): string {
  return process.env.DASHBOARD_API_KEY || "";
}

function safeEqual(left: string, right: string): boolean {
  const a = Buffer.from(left);
  const b = Buffer.from(right);
  return a.length === b.length && timingSafeEqual(a, b);
}

function sessionSignature(expiresAt: number): string {
  const key = apiKey();
  return key ? createHmac("sha256", key).update(`${SESSION_CONTEXT}:${expiresAt}`).digest("base64url") : "";
}

export function verifyAdminKey(candidate: string): boolean {
  const key = apiKey();
  return Boolean(key && candidate && safeEqual(candidate, key));
}

export function adminSessionValue(nowMs = Date.now()): string {
  const expiresAt = nowMs + SESSION_TTL_MS;
  const signature = sessionSignature(expiresAt);
  if (!signature) throw new Error("Dashboard admin auth is not configured");
  return `${expiresAt}.${signature}`;
}

export function hasAdminSession(cookieHeader: string | null, nowMs = Date.now()): boolean {
  const raw = String(cookieHeader || "").split(";").map((item) => item.trim()).find((item) => item.startsWith(`${ADMIN_SESSION_COOKIE}=`));
  if (!raw) return false;
  const supplied = decodeURIComponent(raw.slice(ADMIN_SESSION_COOKIE.length + 1));
  const separator = supplied.indexOf(".");
  if (separator <= 0) return false;
  const expiresAt = Number(supplied.slice(0, separator));
  const signature = supplied.slice(separator + 1);
  if (!Number.isSafeInteger(expiresAt) || expiresAt <= nowMs || expiresAt > nowMs + SESSION_TTL_MS + 60_000) return false;
  const expected = sessionSignature(expiresAt);
  return Boolean(expected && signature && safeEqual(signature, expected));
}

export function requireAdminOrApiAuth(request: Request): NextResponse | null {
  if (hasAdminSession(request.headers.get("cookie"))) return null;
  return requireAuth(request);
}
